import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import pytz
from datetime import datetime

# Set page to wide mode and title
st.set_page_config(
    page_title="TTA Timesheet",
    layout="wide"
)

# Initialize Firebase (only do this once)
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type": st.secrets["firebase"]["type"],
        "project_id": st.secrets["firebase"]["project_id"],
        "private_key_id": st.secrets["firebase"]["private_key_id"],
        "private_key": st.secrets["firebase"]["private_key"],
        "client_email": st.secrets["firebase"]["client_email"],
        "client_id": st.secrets["firebase"]["client_id"],
        "auth_uri": st.secrets["firebase"]["auth_uri"],
        "token_uri": st.secrets["firebase"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
    })
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Initialize session states
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'sidebar_state' not in st.session_state:
    st.session_state.sidebar_state = False
if 'selected_week' not in st.session_state:
    st.session_state.selected_week = None

eastern = pytz.timezone('US/Eastern')

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state.authenticated = True
            st.session_state.sidebar_state = True  # Open sidebar after authentication
            del st.session_state["password"]
        else:
            st.error("😕 Password incorrect")

    if not st.session_state.authenticated:
        st.text_input(
            "Please enter the password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        return False
    return True

if check_password():
    # Get all data from Firestore
    docs = db.collection('sheet').stream()
    records = []
    for doc in docs:
        doc_data = doc.to_dict()
        if 'records' in doc_data:  # Check if document has records array
            for record in doc_data['records']:
                record['id'] = doc.id  # Keep track of which document it came from
                records.append(record)

    df = pd.DataFrame(records)
    if not df.empty and 'Date' in df.columns:
        # Ensure all dates are timezone-aware
        df['Date'] = pd.to_datetime(df['Date'], format='mixed').apply(
            lambda x: x.tz_convert('US/Eastern') if x.tz else x.tz_localize('US/Eastern')
        )
    
    # Initialize user variable
    user = "Stacey"
    colwidth = 90
    
    # Sidebar for user selection
    with st.sidebar:
        default_users = ["Stacey", "Aaron", "Daisy","Cindy", "Alan"]
        user = st.selectbox(
            "Select User",
            options=["Select a user"] + default_users,
            key="user_select",
            index=default_users.index("Stacey") + 1  # +1 because of "Select a user" option
        )
        if user != "Select a user":
            st.success(f"Hours for {user} successfully loaded. Please close sidebar with arrow above.")

    # Display the logo
    st.image(
        "tta_logo.png",  # Replace with the path to your logo
        width=200,  # Adjust width as needed
        use_column_width=False
    )

    # Main content
    if user != "Select a user":        
        # Add title
        st.title(f"{'Viewing' if user == 'Alan' else f'Hours for {user}'}")
        
        # Get current date and create future dates
        current_date = pd.Timestamp.now()
        future_date = current_date + pd.Timedelta(weeks=20)

        all_dates = pd.date_range(
            start=current_date,
            end=future_date,
            freq='D'
        )
        
        # Convert to DataFrame to match user_df structure
        all_dates_df = pd.DataFrame({'Date': all_dates})
        
        # Get unique weeks starting on Tuesday
        dates = all_dates_df['Date'].dt.to_period('W-TUE').unique()
        dates = dates[::2]  # Skip every other week
        week_starts = [date.start_time.strftime('%m/%d/%Y') for date in dates]
        
        # Find the current bi-weekly period
        current_date = pd.Timestamp.now()
        current_period = current_date.to_period('W-TUE')
        current_period_start = current_period.start_time

        # If current date is before the period start, adjust back
        if current_date < current_period_start:
            current_period_start -= pd.Timedelta(weeks=2)

        # Format current period start to match week_starts format
        current_period_str = current_period_start.strftime('%m/%d/%Y')

        # Find the closest past week start (or today if it's a week start)
        past_weeks = [w for w in week_starts if pd.to_datetime(w) <= current_date]
        if past_weeks:
            default_week = past_weeks[-1]  # Get the most recent past week
            default_index = week_starts.index(default_week)
        else:
            default_index = 0

        # Initialize selected_week in session state if not already set
        if st.session_state.selected_week is None:
            st.session_state.selected_week = week_starts[default_index]

        # Add week selector
        selected_week = st.selectbox(
            "Select Week Beginning",
            options=week_starts,
            format_func=lambda x: f"Week of {x}",
            index=week_starts.index(st.session_state.selected_week),
            key='week_selector'
        )
        
        # Update session state when selection changes
        if selected_week != st.session_state.selected_week:
            st.session_state.selected_week = selected_week

        # Convert selected week to datetime and create full date range
        week_start = pd.to_datetime(selected_week)
        week_end = week_start + pd.Timedelta(days=13)
        
        # Show all users if Alan, otherwise just selected user
        users_to_display = default_users if user == "Alan" else [user]
        
        for current_user in users_to_display:
            if user == "Alan":
                st.subheader(f"Hours for {current_user}")
            
            # Filter for current user and date range
            if not df.empty and 'Date' in df.columns:
                # Convert week_start and week_end to timezone-aware timestamps
                week_start_tz = pd.to_datetime(week_start).tz_localize('US/Eastern')
                week_end_tz = pd.to_datetime(week_end).tz_localize('US/Eastern')
                
                user_df = df[
                    (df['User'] == current_user) & 
                    (df['Date'] >= week_start_tz) &
                    (df['Date'] <= week_end_tz)
                ]
            else:
                user_df = pd.DataFrame(columns=['User', 'Date', 'TimeType', 'Hours', 'LastUpdated', 'EnteredPayment'])
            
            if user == "Alan" and user_df.empty:
                st.info(f"No hours entered for {current_user}")
            
            if not user_df.empty or user != "Alan":
                # Create complete date range
                date_df = pd.DataFrame({
                    'Date': pd.date_range(
                        start=week_start,
                        end=week_end,
                        freq='D'
                    )
                })
                
                # Make date_df timezone-aware to match user_df
                date_df['Date'] = date_df['Date'].dt.tz_localize('US/Eastern')

                # Pivot and prepare data
                pivoted_df = user_df.pivot_table(
                    index='Date',
                    columns='TimeType',
                    values='Hours',
                    aggfunc='sum',
                    fill_value=0
                )
                
                # Merge with complete date range
                pivoted_df = pd.merge(
                    date_df,
                    pivoted_df,
                    left_on='Date',
                    right_index=True,
                    how='left'
                ).fillna(0)
                
                # Ensure all required columns exist and replace None with 0
                for col in ['Regular', 'Holiday', 'Sick', 'Vacation']:
                    if col not in pivoted_df.columns:
                        pivoted_df[col] = 0
                    else:
                        pivoted_df[col] = pivoted_df[col].replace({None: 0})
                
                # Format the dates and limit to 14 rows
                display_df = pivoted_df.reset_index()
                display_df['Date'] = display_df['Date'].dt.strftime('%a %m/%d')
                display_df = display_df.head(14)  # Only take first 14 rows
                
                # Filter out zero rows for Alan's view
                if user == "Alan":
                    display_df = display_df[
                        (display_df['Regular'] != 0) |
                        (display_df['Holiday'] != 0) |
                        (display_df['Sick'] != 0) |
                        (display_df['Vacation'] != 0)
                    ]
                
                if not display_df.empty or user != "Alan":
                    edited_df = st.data_editor(
                        data=display_df[["Date", "Regular", "Sick", "Vacation", "Holiday"]],
                        hide_index=True,
                        use_container_width=False,
                        num_rows="fixed",
                        height=min(38 + len(display_df) * 35, 600),
                        column_config={
                            "Date": st.column_config.TextColumn(
                                "Date",
                                width=75,
                                disabled=True,
                            ),
                            "Regular": st.column_config.NumberColumn(
                                "Regular",
                                width=colwidth-10,
                                min_value=0,
                                max_value=24,
                                step=0.25,
                                format="%.2f"
                            ),
                            "Holiday": st.column_config.NumberColumn(
                                "Holiday",
                                width=colwidth-5,
                                min_value=0,
                                max_value=24,
                                step=0.25,
                                format="%.2f"
                            ),
                            "Sick": st.column_config.NumberColumn(
                                "Sick",
                                width=colwidth-25,
                                min_value=0,
                                max_value=24,
                                step=0.25,
                                format="%.2f"
                            ),
                            "Vacation": st.column_config.NumberColumn(
                                "Vacation",
                                width=colwidth-5,
                                min_value=0,
                                max_value=24,
                                step=0.25,
                                format="%.2f"
                            )
                        },
                        key=f"timesheet_editor_{current_user}",
                        disabled=user == "Alan"
                    )
                    
                    if edited_df is not None and user != "Alan":
                        if st.button("Save Changes", type="primary"):
                            # Create records with timestamp
                            records = []
                            current_timestamp = pd.Timestamp.now(tz=eastern).strftime('%Y-%m-%d %H:%M:%S')
                            
                            for _, row in edited_df.iterrows():
                                # Parse the date correctly using the year from selected_week
                                date_str = row['Date'].split(' ')[1]  # Get '12/11' from 'Wed 12/11'
                                month, day = date_str.split('/')
                                selected_year = week_start.year  # Get year from the selected week
                                full_date = f"{selected_year}-{month}-{day}"
                                
                                # Create a record for each non-zero value
                                for time_type in ['Regular', 'Sick', 'Vacation', 'Holiday']:
                                    hours = row[time_type]  # Get the value directly from the DataFrame
                                    if hours > 0:  # Only add if hours are greater than 0
                                        records.append({
                                            'User': current_user,
                                            'Date': full_date,
                                            'TimeType': time_type,
                                            'Hours': float(hours),  # Ensure it's a float
                                            'LastUpdated': current_timestamp,
                                            'EnteredPayment': ''  # Default to empty string for false
                                        })
                            
                            # Get all existing data
                            existing_docs = db.collection('sheet').stream()
                            all_data = {}
                            for doc in existing_docs:
                                doc_data = doc.to_dict()
                                if 'records' in doc_data:
                                    user = doc.id
                                    all_data[user] = doc_data['records']

                            # Filter out records for current user and date range
                            if current_user in all_data:
                                filtered_data = [
                                    record for record in all_data[current_user]
                                    if not (
                                        pd.to_datetime(record['Date']).tz_localize('US/Eastern') >= week_start.tz_localize('US/Eastern') and
                                        pd.to_datetime(record['Date']).tz_localize('US/Eastern') <= week_end.tz_localize('US/Eastern')
                                    )
                                ]
                            else:
                                filtered_data = []

                            # Add new records
                            filtered_data.extend(records)

                            # Update the document for current user
                            db.collection('sheet').document(current_user).set({
                                'records': filtered_data
                            })

                            # Reload the data
                            st.rerun()
                    
                    # Add caption and calculate sums
                    st.subheader(f"Bi-weekly Totals for the week of {selected_week} - {week_end.strftime('%m/%d/%Y')}")
                    sums_df = pd.DataFrame({
                        'Date': ['Totals'],
                        'Regular': [display_df['Regular'].sum()],
                        'Sick': [display_df['Sick'].sum()],
                        'Vacation': [display_df['Vacation'].sum()],
                        'Holiday': [display_df['Holiday'].sum()]
                    })
                    
                    # Display sums
                    st.data_editor(
                        data=sums_df,
                        hide_index=True,
                        use_container_width=False,
                        num_rows="fixed",
                        column_config={
                            "Date": st.column_config.TextColumn(
                                "Date",
                                width=75,
                                disabled=True,
                            ),
                            "Regular": st.column_config.NumberColumn(
                                "Regular",
                                width=colwidth-10,
                                disabled=True,
                                format="%.2f"
                            ),
                            "Holiday": st.column_config.NumberColumn(
                                "Holiday",
                                width=colwidth-5,
                                disabled=True,
                                format="%.2f"
                            ),
                            "Sick": st.column_config.NumberColumn(
                                "Sick",
                                width=colwidth-25,
                                disabled=True,
                                format="%.2f"
                            ),
                            "Vacation": st.column_config.NumberColumn(
                                "Vacation",
                                width=colwidth-5,
                                disabled=True,
                                format="%.2f"
                            )
                        },
                        key=f"sums_editor_{current_user}"
                    )
                    
                    # Display last updated time
                    if not df.empty and 'LastUpdated' in df.columns:
                        last_updated = df[
                            (df['User'] == current_user)
                        ]['LastUpdated'].max()
                        if pd.notna(last_updated) and last_updated is not None:
                            try:
                                formatted_time = pd.to_datetime(last_updated, format='%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y at %I:%M %p')
                                st.info(f"Last updated: {formatted_time}")
                            except:
                                st.info("No previous updates")
                        else:
                            st.info("No previous updates")
                    else:
                        st.info("No previous updates")

        # Add "Entered for Payment" button at the very bottom of the page for Alan's view
        if user == "Alan":
            st.markdown("---")  # Add a visual separator
            
            # Check if all displayed rows are already entered for payment
            current_period_data = [
                row for row in docs.to_dict() 
                if (
                    row['User'] in users_to_display and
                    pd.to_datetime(row['Date']).tz_localize('UTC') >= pd.to_datetime(week_start).tz_localize('UTC') and
                    pd.to_datetime(row['Date']).tz_localize('UTC') <= pd.to_datetime(week_end).tz_localize('UTC') and
                    float(row.get('Hours', 0)) > 0
                )
            ]
            
            # Check if any row in the period has EnteredPayment
            payment_entered = any(
                row.get('EnteredPayment', '') != '' 
                for row in current_period_data
            ) if current_period_data else False
            
            if payment_entered:
                try:
                    # Get the latest payment timestamp from all rows in current period
                    payment_times = [pd.to_datetime(row.get('EnteredPayment')) 
                                   for row in current_period_data 
                                   if pd.notna(pd.to_datetime(row.get('EnteredPayment', '')))]
                    if payment_times:
                        latest_payment = max(payment_times)
                        formatted_time = latest_payment.strftime('%B %d, %Y at %I:%M %p')
                        st.success(f"All hours in this period have been entered for payment on {formatted_time}")
                    else:
                        st.success("All hours in this period have been entered for payment")
                except (ValueError, AttributeError, KeyError):
                    st.success("All hours in this period have been entered for payment")
            elif st.button("Enter for Payment", type="primary", key="payment_button"):
                # Get all existing data
                all_data = docs.to_dict()
                
                # Update EnteredPayment to datetime for matching rows
                updated_data = []
                payment_timestamp = pd.Timestamp.now(tz=eastern).strftime('%Y-%m-%d %H:%M:%S')
                for row in all_data:
                    if (
                        row['User'] in users_to_display and
                        pd.to_datetime(row['Date']).tz_localize('UTC') >= pd.to_datetime(week_start).tz_localize('UTC') and
                        pd.to_datetime(row['Date']).tz_localize('UTC') <= pd.to_datetime(week_end).tz_localize('UTC')
                    ):
                        row['EnteredPayment'] = payment_timestamp
                    updated_data.append(row)
                
                # Clear and update sheet
                db.collection('sheet').document(user).set(updated_data)
                
                formatted_time = pd.to_datetime(payment_timestamp).strftime('%B %d, %Y at %I:%M %p')
                st.success(f"Payment entry recorded for all users in selected period on {formatted_time}")

                 # Add "Reset Week" button
            if st.button("Reset Week", type="secondary", key="reset_week_button"):
                # Get all existing data
                all_data = docs.to_dict()
                
                # Update EnteredPayment to empty for matching rows
                updated_data = []
                # st.write(all_data)
                for row in all_data:
                    # st.write(row)
                    if (
                        row['User'] in users_to_display and
                        pd.to_datetime(row['Date']).tz_localize('UTC') >= pd.to_datetime(week_start).tz_localize('UTC') and
                        pd.to_datetime(row['Date']).tz_localize('UTC') <= pd.to_datetime(week_end).tz_localize('UTC') and
                        float(row.get('Hours', 0)) > 0
                    ):
                    
                        row['EnteredPayment'] = ''  # Reset the EnteredPayment field
                    updated_data.append(row)
                
                # Clear and update sheet
                db.collection('sheet').document(user).set(updated_data)
                
                # st.success("Payment entries have been reset for the selected period.")
                st.rerun()
    else:
        st.write("Please select a user")
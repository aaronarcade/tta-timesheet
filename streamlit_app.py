import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Set page to wide mode and title
st.set_page_config(
    page_title="TTA Timesheet",
    layout="wide"
)

# Initialize session states
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'sidebar_state' not in st.session_state:
    st.session_state.sidebar_state = False

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
    # Set up Google Sheets authentication
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(credentials)

    # Open the Google Sheet (replace with your sheet URL or key)
    sheet = client.open_by_key('1GVEPaF4Tzw84s7tGyp8tNCxzqNO6u9QntLKQ5_oatOM').sheet1

    # Get all data
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Convert Date column to datetime
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Initialize user variable
    user = "Stacey"
    colwidth = 85
    
    # Sidebar for user selection
    with st.sidebar:
        st.image("tta_logo.png", width=200)
        users = df['User'].unique().tolist()
        user = st.selectbox(
            "Select User",
            options=["Select a user"] + users,
            key="user_select",
            index=users.index("Stacey") + 1  # +1 because of "Select a user" option
        )
        if user != "Select a user":
            st.success(f"Hours for {user} successfully loaded. Please close sidebar with arrow above.")

    # Main content
    if user != "Select a user":        
        # Add title
        st.title(f"{'Viewing' if user == 'Alan' else f'Entering Hours for {user}'}")
        
        # Get current date and create future dates
        current_date = pd.Timestamp.now()
        future_date = current_date + pd.Timedelta(weeks=20)
        
        # Create date range including future dates
        all_dates = pd.date_range(
            start=df['Date'].min(),
            end=future_date,
            freq='D'
        )
        
        # Convert to DataFrame to match user_df structure
        all_dates_df = pd.DataFrame({'Date': all_dates})
        
        # Get unique weeks starting on Tuesday
        dates = all_dates_df['Date'].dt.to_period('W-TUE').unique()
        dates = dates[::2]  # Skip every other week
        week_starts = [date.start_time.strftime('%m/%d/%Y') for date in dates]
        
        # Add week selector
        selected_week = st.selectbox(
            "Select Week Beginning",
            options=week_starts,
            format_func=lambda x: f"Week of {x}"
        )
        
        # Convert selected week to datetime and create full date range
        week_start = pd.to_datetime(selected_week)
        week_end = week_start + pd.Timedelta(days=13)
        
        # Show all users if Alan, otherwise just selected user
        users_to_display = users if user == "Alan" else [user]
        
        for current_user in users_to_display:
            if user == "Alan":
                st.subheader(f"Hours for {current_user}")
            
            # Filter for current user and date range
            user_df = df[
                (df['User'] == current_user) & 
                (df['Date'] >= week_start) & 
                (df['Date'] <= week_end)
            ]
            
            if not user_df.empty or user != "Alan":
                # Pivot and prepare data
                pivoted_df = user_df.pivot_table(
                    index='Date',
                    columns='TimeType',
                    values='Hours',
                    aggfunc='sum',
                    fill_value=0
                )
                
                # Create complete date range
                date_df = pd.DataFrame({'Date': pd.date_range(start=week_start, end=week_end, freq='D')})
                
                # Merge with complete date range
                pivoted_df = pd.merge(
                    date_df.set_index('Date'),
                    pivoted_df,
                    left_index=True,
                    right_index=True,
                    how='left'
                ).fillna(0)
                
                # Ensure all required columns exist
                for col in ['Regular', 'Holiday', 'Sick', 'Vacation']:
                    if col not in pivoted_df.columns:
                        pivoted_df[col] = 0
                
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
                        data=display_df[["Date", "Regular", "Holiday", "Sick", "Vacation"]],
                        hide_index=True,
                        use_container_width=False,
                        num_rows="fixed",
                        height=min(0 + len(display_df) * 35, 600),
                        column_config={
                            "Date": st.column_config.TextColumn(
                                "Date",
                                width=75,
                                disabled=True,
                            ),
                            "Regular": st.column_config.NumberColumn(
                                "Regular",
                                width=colwidth,
                                min_value=0,
                                max_value=24,
                                step=1,
                            ),
                            "Holiday": st.column_config.NumberColumn(
                                "Holiday",
                                width=colwidth,
                                min_value=0,
                                max_value=24,
                                step=1,
                            ),
                            "Sick": st.column_config.NumberColumn(
                                "Sick",
                                width=colwidth,
                                min_value=0,
                                max_value=24,
                                step=1,
                            ),
                            "Vacation": st.column_config.NumberColumn(
                                "Vacation",
                                width=colwidth,
                                min_value=0,
                                max_value=24,
                                step=1,
                            )
                        },
                        key=f"timesheet_editor_{current_user}",
                        disabled=user == "Alan"
                    )
                    
                    if edited_df is not None and user != "Alan":
                        if st.button("Save Changes", type="primary"):
                            st.toast(f"Hours saved for week of {selected_week}", icon="✅")
                            st.balloons()
                            # Update display_df with edited values for totals
                            display_df = edited_df
                    
                    # Add caption and calculate sums
                    st.caption("Bi-weekly Totals")
                    sums_df = pd.DataFrame({
                        'Date': ['Total Hours'],
                        'Regular': [display_df['Regular'].sum()],
                        'Holiday': [display_df['Holiday'].sum()],
                        'Sick': [display_df['Sick'].sum()],
                        'Vacation': [display_df['Vacation'].sum()]
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
                                width=colwidth,
                                disabled=True,
                            ),
                            "Holiday": st.column_config.NumberColumn(
                                "Holiday",
                                width=colwidth,
                                disabled=True,
                            ),
                            "Sick": st.column_config.NumberColumn(
                                "Sick",
                                width=colwidth,
                                disabled=True,
                            ),
                            "Vacation": st.column_config.NumberColumn(
                                "Vacation",
                                width=colwidth,
                                disabled=True,
                            )
                        },
                        key=f"sums_editor_{current_user}"
                    )
    else:
        st.write("Please select a user")
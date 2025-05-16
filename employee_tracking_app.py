import streamlit as st
import pandas as pd
import altair as alt
from io import StringIO
from datetime import timedelta
from math import ceil

st.title("Employee Tracking App")

# Upload Section
uploaded_employee_file = st.file_uploader("Upload Employee Tracking Data (Excel or CSV)", type=["csv", "xlsx"])
uploaded_video_file = st.file_uploader("Upload SME Video Duration Data (Excel or CSV)", type=["csv", "xlsx"])

@st.cache_data
def load_file(file):
    if file.name.endswith('.csv'):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)

# =========================== Load and Preprocess ===========================
if uploaded_employee_file:
    employee_df = load_file(uploaded_employee_file)

    # Standardize column names
    employee_df.columns = employee_df.columns.str.strip().str.lower().str.replace(' ', '_')

    # Check required columns
    required = ['start_date', 'end_date', 'work_days', 'leave_days', 'topic', 'name']
    if not all(col in employee_df.columns for col in required):
        st.error(f"Missing columns: {set(required) - set(employee_df.columns)}")
        st.stop()

    # Convert dates
    employee_df['start_date'] = pd.to_datetime(employee_df['start_date'], errors='coerce')
    employee_df['end_date'] = pd.to_datetime(employee_df['end_date'], errors='coerce')
    employee_df.dropna(subset=['start_date'], inplace=True)

    # Add temporal features
    employee_df['week_number'] = employee_df['start_date'].dt.isocalendar().week
    employee_df['month'] = employee_df['start_date'].dt.month_name()
    employee_df['month_number'] = employee_df['start_date'].dt.month

    # Sidebar Navigation
    st.sidebar.title("Menu")
    menu = ["Weekly Performance", "Monthly Performance", "Overall Statistics", "Attendance", "PPT, Illustration & AE Buffer", "Video Duration"]
    choice = st.sidebar.radio("Go to", menu)

    # ======================== Weekly Performance ========================
    if choice == "Weekly Performance":
        st.subheader("Weekly Performance")

        weekly_summary = employee_df.groupby(['name', 'week_number']).agg(
            total_work_days=('work_days', 'sum'),
            total_leave_days=('leave_days', 'sum'),
            ppt_count=('topic', 'count')
        ).reset_index()

        weekly_summary['weekly_target'] = 6
        weekly_summary['target_met'] = weekly_summary['ppt_count'] >= weekly_summary['weekly_target']

        st.dataframe(weekly_summary)
        st.download_button("Download Weekly Summary", weekly_summary.to_csv(index=False), "weekly_summary.csv")

        chart = alt.Chart(weekly_summary).mark_bar().encode(
            x='week_number:O',
            y='ppt_count:Q',
            color=alt.condition(alt.datum.target_met, alt.value('green'), alt.value('red')),
            tooltip=['name', 'ppt_count', 'weekly_target', 'target_met']
        ).properties(title="Weekly Topic Coverage")
        st.altair_chart(chart, use_container_width=True)

    # ======================== Monthly Performance ========================
    elif choice == "Monthly Performance":
        st.subheader("Monthly Performance")

        monthly_summary = employee_df.groupby(['name', 'month', 'month_number']).agg(
            total_work_days=('work_days', 'sum'),
            total_leave_days=('leave_days', 'sum'),
            ppt_count=('topic', 'nunique'),
            unique_weeks=('week_number', pd.Series.nunique)
        ).reset_index()

        monthly_summary['monthly_target'] = monthly_summary['unique_weeks'] * 6
        monthly_summary['target_met'] = monthly_summary['ppt_count'] >= monthly_summary['monthly_target']

        st.dataframe(monthly_summary)
        st.download_button("Download Monthly Summary", monthly_summary.to_csv(index=False), "monthly_summary.csv")

        month_order = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        chart = alt.Chart(monthly_summary).mark_bar().encode(
            x=alt.X('month:O', sort=month_order),
            y='ppt_count:Q',
            color=alt.condition(alt.datum.target_met, alt.value('green'), alt.value('red')),
            tooltip=['name', 'ppt_count', 'monthly_target', 'target_met']
        ).properties(title="Monthly Topic Coverage")
        st.altair_chart(chart, use_container_width=True)

    # ======================== Overall Statistics ========================
    elif choice == "Overall Statistics":
        st.subheader("Overall Statistics")
        summary = employee_df.groupby('name').agg(
            total_work_days=('work_days', 'sum'),
            total_leave_days=('leave_days', 'sum'),
            total_ppt_count=('topic', 'nunique')
        ).reset_index()

        st.dataframe(summary)
        st.download_button("Download Overall Summary", summary.to_csv(index=False), "overall_summary.csv")

        chart = alt.Chart(summary).mark_bar().encode(
            x='name:N',
            y='total_ppt_count:Q',
            tooltip=['name', 'total_ppt_count']
        ).properties(title="Total Topics Covered")
        st.altair_chart(chart, use_container_width=True)

    # ======================== Attendance ========================
    elif choice == "Attendance":
        st.subheader("Attendance Summary")

        attendance = employee_df.groupby(['name', 'month']).agg(
            total_days=('start_date', 'count'),
            work_days=('work_days', 'sum'),
            leave_days=('leave_days', 'sum')
        ).reset_index()
        attendance['present_days'] = attendance['work_days']
        attendance['absent_days'] = attendance['total_days'] - attendance['present_days']

        st.dataframe(attendance)

        emp = st.selectbox("Select Employee", attendance['name'].unique())
        emp_att = attendance[attendance['name'] == emp].iloc[0]

        pie_data = pd.DataFrame({
            'Status': ['Present', 'Absent', 'Leave'],
            'Days': [emp_att['present_days'], emp_att['absent_days'], emp_att['leave_days']]
        })

        chart = alt.Chart(pie_data).mark_arc().encode(
            theta="Days:Q",
            color="Status:N",
            tooltip=["Status", "Days"]
        ).properties(title=f"Attendance for {emp}")
        st.altair_chart(chart, use_container_width=True)

    # ======================== Buffer Summary ========================
    elif choice == "PPT, Illustration & AE Buffer":
        st.subheader("📄🎨🎬 PPT, Illustration & AE Buffer")

        if all(col in employee_df.columns for col in ["ppt's_buffer", "lab_ppt's_buffer", "illu_buffer", "ae_buffer"]):
            buffer_cols = ["ppt's_buffer", "lab_ppt's_buffer", "illu_buffer", "ae_buffer"]

            buffer_summary = employee_df[['name'] + buffer_cols].copy()
            buffer_summary = buffer_summary.groupby('name')[buffer_cols].sum().reset_index()

            st.dataframe(buffer_summary)

            # Melt for visualization
            melted = buffer_summary.melt(id_vars='name', var_name='Buffer Type', value_name='Count')
            melted['Buffer Type'] = melted['Buffer Type'].str.replace('_', ' ').str.title()

            chart = alt.Chart(melted).mark_bar().encode(
                x='name:N',
                y='Count:Q',
                color='Buffer Type:N',
                tooltip=['name', 'Buffer Type', 'Count']
            ).properties(title="Buffer Counts per Employee")
            st.altair_chart(chart, use_container_width=True)
        else:
            st.warning("Required buffer columns not found in the data.")

    # ======================== Video Duration ========================
    elif choice == "Video Duration":
        st.subheader("Video Duration by SME")

        if uploaded_video_file:
            video_df = load_file(uploaded_video_file)
            video_df.columns = video_df.columns.str.strip().str.lower().str.replace(' ', '_')

            if {'name', 'video_duration'}.issubset(video_df.columns):
                def time_to_minutes(t):
                    if isinstance(t, str):
                        parts = t.split(":")
                        try:
                            if len(parts) == 2:
                                return int(parts[0]) + int(parts[1]) / 60
                            elif len(parts) == 3:
                                return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60
                        except:
                            return 0
                    return 0

                video_df['total_minutes'] = video_df['video_duration'].apply(time_to_minutes)

                video_summary = video_df.groupby('name')['total_minutes'].sum().reset_index()
                video_summary['target_minutes'] = 90
                video_summary['target_met'] = video_summary['total_minutes'] >= video_summary['target_minutes']

                st.dataframe(video_summary)

                chart = alt.Chart(video_summary).mark_bar().encode(
                    x='name:N',
                    y='total_minutes:Q',
                    color=alt.condition(alt.datum.target_met, alt.value('green'), alt.value('red')),
                    tooltip=['name', 'total_minutes', 'target_minutes']
                ).properties(title="Total Video Duration (in minutes)")
                st.altair_chart(chart, use_container_width=True)

                emp = st.selectbox("Select SME", video_summary['name'].unique())
                emp_dur = video_summary[video_summary['name'] == emp].iloc[0]
                st.metric(
                    label=f"Video Duration for {emp}",
                    value=f"{emp_dur['total_minutes']:.1f} mins",
                    delta=f"{emp_dur['total_minutes'] - emp_dur['target_minutes']:.1f} mins from target"
                )
            else:
                st.error("Video file must contain 'name' and 'video_duration' columns.")
        else:
            st.info("Upload a video duration file to view this section.")

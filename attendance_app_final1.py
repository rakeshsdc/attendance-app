import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="FYUGP Attendance App", layout="wide")
st.title("📘 FYUGP Attendance Management System")

@st.cache_data
def load_data():
    students = pd.read_csv("students.csv")
    courses = pd.read_csv("courses.csv")
    teachers = pd.read_csv("teachers.csv")
    try:
        attendance = pd.read_csv("attendance.csv")
    except FileNotFoundError:
        attendance = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by"])
    try:
        camp_days = pd.read_csv("camp_days.csv", parse_dates=["start_date", "end_date"])
    except FileNotFoundError:
        camp_days = pd.DataFrame(columns=["student_id", "start_date", "end_date", "activity"])
    return students, courses, teachers, attendance, camp_days

students, courses, teachers, attendance, camp_days = load_data()

# Sidebar Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.header("🔐 Login")
    email_input = st.sidebar.text_input("Email").strip().lower()
    password_input = st.sidebar.text_input("Password", type="password").strip()
    if st.sidebar.button("Login"):
        match = teachers[
            (teachers["email"].str.strip().str.lower() == email_input) &
            (teachers["password"].astype(str).str.strip() == password_input)
        ]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.teacher_name = match.iloc[0]["name"]
            st.session_state.teacher_id = match.iloc[0]["teacher_id"]
            st.session_state.role = match.iloc[0]["role"]
            st.session_state.department = match.iloc[0].get("department", "")
            st.sidebar.success("Login successful!")
        else:
            st.sidebar.error("Invalid credentials.")
else:
    st.sidebar.success(f"👋 Logged in as: {st.session_state.teacher_name}")
    if st.sidebar.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

if st.session_state.get("logged_in", False):
    st.success(f"Welcome, {st.session_state.teacher_name}! Role: {st.session_state.role.title()}")

    # Show Take Attendance if teacher (or admin with courses)
    teacher_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
    if not teacher_courses.empty:
        st.subheader("📝 Take Attendance")
        selected_course = st.selectbox("Select your course:", teacher_courses["course_id"])
        if selected_course:
            enrolled = students[
                (students["major_course"] == selected_course) |
                (students["minor1_course"] == selected_course) |
                (students["minor2_course"] == selected_course) |
                (students["mdc_course"] == selected_course) |
                (students["vac_course"] == selected_course)
            ]
            selected_date = st.date_input("Date", value=date.today())
            selected_hour = st.number_input("Hour (1-6)", min_value=1, max_value=6)

            attendance_options = ["P", "A", "NSS", "NCC", "Club"]
            student_status = {}
            for _, row in enrolled.iterrows():
                label = f"{row['name']} ({row['student_id']})"
                student_status[row["student_id"]] = st.selectbox(
                    f"{label}", attendance_options, key=f"{row['student_id']}_{selected_hour}"
                )

            if st.button("💾 Save Attendance"):
                records = []
                for sid, status in student_status.items():
                    records.append({
                        "date": selected_date,
                        "hour": selected_hour,
                        "course_id": selected_course,
                        "student_id": sid,
                        "status": status,
                        "marked_by": st.session_state.teacher_id
                    })
                new_df = pd.DataFrame(records)
                attendance = pd.concat([attendance, new_df], ignore_index=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("✅ Attendance saved.")

    # Camp Days Entry
    if st.session_state.role in ["admin", "dept_admin"]:
        st.subheader("🛡 Enter Camp Days")
        st.info("These days will be excluded from total session count for the student.")
        student_options = students[["student_id", "name"]].apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1)
        selected_student = st.selectbox("Student", student_options)
        selected_id = selected_student.split("(")[-1].strip(")")
        start_camp = st.date_input("Start Date")
        end_camp = st.date_input("End Date")
        activity = st.selectbox("Activity", ["NSS", "NCC", "Club"])
        if st.button("➕ Add Camp Record"):
            new_row = pd.DataFrame([{
                "student_id": selected_id,
                "start_date": pd.to_datetime(start_camp),
                "end_date": pd.to_datetime(end_camp),
                "activity": activity
            }])
            camp_days = pd.concat([camp_days, new_row], ignore_index=True)
            camp_days.to_csv("camp_days.csv", index=False)
            st.success("✅ Camp entry saved.")

        if not camp_days.empty:
            st.write("### Camp Records")
            st.dataframe(camp_days)

    # Reports
    st.subheader("📊 Attendance Reports")
    date_range = st.date_input("Date Range", [date(2025, 7, 1), date.today()])
    if len(date_range) == 2:
        start_dt = pd.to_datetime(date_range[0])
        end_dt = pd.to_datetime(date_range[1])
        filt_attendance = attendance[pd.to_datetime(attendance["date"]).between(start_dt, end_dt)]
        filt_attendance["date"] = pd.to_datetime(filt_attendance["date"])

        def is_camp_day(sid, dt):
            rows = camp_days[camp_days["student_id"] == sid]
            return any((dt >= row["start_date"]) and (dt <= row["end_date"]) for _, row in rows.iterrows())

        attendance_no_camp = filt_attendance[~filt_attendance.apply(lambda x: is_camp_day(x["student_id"], x["date"]), axis=1)]

        detailed = pd.merge(attendance_no_camp, students, on="student_id")[["date", "hour", "student_id", "name", "course_id", "status"]]
        st.write("### Detailed Attendance (excluding camp days)")
        st.dataframe(detailed)
        st.download_button("📥 Download Detailed", detailed.to_csv(index=False), "detailed.csv")

        summary = attendance_no_camp.groupby("student_id")["status"].agg([
            ("Total", "count"),
            ("Present", lambda x: (x != "A").sum())
        ]).reset_index()
        summary["Percentage"] = (summary["Present"] / summary["Total"] * 100).round(2)
        summary = pd.merge(summary, students, on="student_id")[["student_id", "name", "Total", "Present", "Percentage"]]
        st.write("### Summary Report")
        st.dataframe(summary)
        st.download_button("📥 Download Summary", summary.to_csv(index=False), "summary.csv")

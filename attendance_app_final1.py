# FYUGP Attendance Streamlit App - Phase 5 (Fixed login + date filtering)

import streamlit as st
import pandas as pd
from datetime import date

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
    return students, courses, teachers, attendance

students, courses, teachers, attendance = load_data()

# --- Login ---
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
        st.write("🔍 Debug:", st.session_state.teacher_id, "-", st.session_state.role)
    else:
        st.sidebar.error("Invalid credentials")

if st.session_state.get("logged_in", False):
    st.success(f"Welcome, {st.session_state.teacher_name}! Role: {st.session_state.role.title()}")

    if st.session_state.role == "teacher":
        # --- Teacher Interface ---
        my_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
        selected_course = st.selectbox("Select a course to manage attendance:", my_courses["course_id"])

        if selected_course:
            course_info = courses[courses["course_id"] == selected_course].iloc[0]
            enrolled = students[
                (students["major_course"] == selected_course) |
                (students["minor1_course"] == selected_course) |
                (students["minor2_course"] == selected_course) |
                (students["mdc_course"] == selected_course) |
                (students["vac_course"] == selected_course)
            ]

            st.subheader("📝 Take Attendance")
            selected_date = st.date_input("Select Date", value=date.today())
            selected_hour = st.number_input("Hour (1-6)", min_value=1, max_value=6, step=1)
            absent_ids = st.multiselect("Select Absent Students", options=enrolled["student_id"].tolist(), default=[])

            if st.button("Save Attendance"):
                records = []
                for _, row in enrolled.iterrows():
                    status = "A" if row["student_id"] in absent_ids else "P"
                    records.append({
                        "date": selected_date,
                        "hour": selected_hour,
                        "course_id": selected_course,
                        "student_id": row["student_id"],
                        "status": status,
                        "marked_by": st.session_state.teacher_id
                    })
                new_df = pd.DataFrame(records)
                attendance = pd.concat([attendance, new_df], ignore_index=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("✅ Attendance saved successfully!")

            st.subheader("📊 Attendance Reports")
            date_range = st.date_input("Select Date Range", [date(2025, 7, 1), date.today()])
            if len(date_range) == 2:
                start, end = date_range
                start_dt = pd.to_datetime(start)
                end_dt = pd.to_datetime(end)
                filtered = attendance[
                    (attendance["course_id"] == selected_course) &
                    (pd.to_datetime(attendance["date"]).between(start_dt, end_dt))
                ]
                if not filtered.empty:
                    detailed = pd.merge(filtered, students, on="student_id")[
                        ["date", "hour", "student_id", "name", "status"]
                    ]
                    st.write("### Detailed Report")
                    st.dataframe(detailed)
                    st.download_button("📥 Download Detailed", detailed.to_csv(index=False), "detailed.csv")

                    summary = filtered.groupby("student_id")["status"].agg([
                        ("Total", "count"),
                        ("Present", lambda x: (x == "P").sum())
                    ]).reset_index()
                    summary["Percentage"] = (summary["Present"] / summary["Total"] * 100).round(2)
                    summary = pd.merge(summary, students, on="student_id")[["student_id", "name", "Total", "Present", "Percentage"]]
                    st.write("### Summary Report")
                    st.dataframe(summary)
                    st.download_button("📥 Download Summary", summary.to_csv(index=False), "summary.csv")
                else:
                    st.info("No records found.")

    elif st.session_state.role in ["admin", "dept_admin"]:
        st.subheader("🏛 Admin Dashboard")
        if st.session_state.role == "admin":
            departments = sorted(students["major_course"].unique())
            selected_major = st.selectbox("Select Department", departments)
        else:
            selected_major = st.session_state.department
            st.info(f"📌 Department Restricted: {selected_major}")

        majors = students[students["major_course"] == selected_major]
        major_ids = majors["student_id"].tolist()

        date_range = st.date_input("Select Date Range", [date(2025, 7, 1), date.today()])
        if len(date_range) == 2:
            start, end = date_range
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            filtered = attendance[
                (attendance["student_id"].isin(major_ids)) &
                (pd.to_datetime(attendance["date"]).between(start_dt, end_dt))
            ]
            if not filtered.empty:
                detail_all = pd.merge(filtered, students, on="student_id")[
                    ["date", "hour", "student_id", "name", "course_id", "status"]
                ]
                st.write("### Full Details")
                st.dataframe(detail_all)
                st.download_button("📥 Download Full Detail", detail_all.to_csv(index=False), "dept_detailed.csv")

                summary_all = filtered.groupby("student_id")["status"].agg([
                    ("Total", "count"),
                    ("Present", lambda x: (x == "P").sum())
                ]).reset_index()
                summary_all["Percentage"] = (summary_all["Present"] / summary_all["Total"] * 100).round(2)
                summary_all = pd.merge(summary_all, students, on="student_id")[["student_id", "name", "Total", "Present", "Percentage"]]
                st.write("### Consolidated Report")
                st.dataframe(summary_all)
                st.download_button("📥 Download Summary", summary_all.to_csv(index=False), "dept_summary.csv")
            else:
                st.info("No attendance data found.")
else:
    st.warning("Please log in to access features.")

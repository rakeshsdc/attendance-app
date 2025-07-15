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
        attendance = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"])
    try:
        camp_days = pd.read_csv("camp_days.csv", parse_dates=["start_date", "end_date"])
    except FileNotFoundError:
        camp_days = pd.DataFrame(columns=["student_id", "start_date", "end_date", "activity"])
    return students, courses, teachers, attendance, camp_days

students, courses, teachers, attendance, camp_days = load_data()

# ✅ SESSION STATE INITIALIZATION
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ✅ LOGIN PAGE
if not st.session_state.logged_in:
    st.sidebar.header("🔐 Login")
    email = st.sidebar.text_input("Email").strip().lower()
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        match = teachers[
            (teachers["email"].str.strip().str.lower() == email) &
            (teachers["password"].astype(str).str.strip() == password)
        ]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.teacher_id = match.iloc[0]["teacher_id"]
            st.session_state.teacher_name = match.iloc[0]["name"]
            st.session_state.role = match.iloc[0]["role"]
            st.session_state.department = match.iloc[0].get("department", "")
            st.sidebar.success(f"Welcome {st.session_state.teacher_name}")
        else:
            st.sidebar.error("Invalid login")

# ✅ AFTER LOGIN
else:
    st.sidebar.success(f"👋 {st.session_state.teacher_name}")
    if st.sidebar.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

    st.markdown(f"**Logged in as:** {st.session_state.teacher_name} ({st.session_state.role})")

    # ✅ TAKE ATTENDANCE
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
            ].copy()

            selected_date = st.date_input("Date", value=date.today())
            existing = attendance[attendance["date"] == str(selected_date)]

            # Mask hours if attendance already marked for the selected course
            all_hours = [str(h) for h in range(1, 7)]
            used_hours = existing[existing["course_id"] == selected_course]["hour"].unique().tolist()
            available_hours = [h for h in all_hours if h not in used_hours]
            available_hours.append("Extra Hour")

            selected_hour = st.selectbox("Select Hour", available_hours)
            extra_time = ""
            duration = ""

            if selected_hour == "Extra Hour":
                extra_time = st.time_input("Start Time")
                duration = st.number_input("Duration (min)", min_value=10, max_value=180)

            # Status inputs
            student_labels = enrolled.apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1).tolist()
            absent = st.multiselect("Absent (A)", student_labels)
            nss = st.multiselect("NSS", student_labels)
            ncc = st.multiselect("NCC", student_labels)
            club = st.multiselect("Club", student_labels)

            if st.button("💾 Save Attendance"):
                records = []
                for _, row in enrolled.iterrows():
                    sid = row["student_id"]
                    label = f"{row['name']} ({sid})"
                    if label in absent:
                        status = "A"
                    elif label in nss:
                        status = "NSS"
                    elif label in ncc:
                        status = "NCC"
                    elif label in club:
                        status = "Club"
                    else:
                        status = "P"
                    records.append({
                        "date": selected_date,
                        "hour": selected_hour,
                        "course_id": selected_course,
                        "student_id": sid,
                        "status": status,
                        "marked_by": st.session_state.teacher_id,
                        "extra_time": str(extra_time),
                        "duration": duration
                    })
                # Remove duplicates
                attendance = attendance[~(
                    (attendance["date"] == str(selected_date)) &
                    (attendance["hour"] == selected_hour) &
                    (attendance["course_id"] == selected_course)
                )]
                attendance = pd.concat([attendance, pd.DataFrame(records)], ignore_index=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("✅ Attendance saved.")

    # ✅ ATTENDANCE DELETION (Admin)
    if st.session_state.role in ["admin", "dept_admin"]:
        st.subheader("🗑 Delete Attendance")
        del_course = st.selectbox("Select Course", courses["course_id"].unique())
        del_date = st.date_input("Delete from Date", value=date.today())
        del_hour = st.selectbox("Hour to Delete", options=["All"] + [str(h) for h in range(1, 7)])
        if st.button("❌ Delete Attendance"):
            if del_hour == "All":
                attendance = attendance[~(
                    (attendance["course_id"] == del_course) &
                    (attendance["date"] == str(del_date))
                )]
            else:
                attendance = attendance[~(
                    (attendance["course_id"] == del_course) &
                    (attendance["date"] == str(del_date)) &
                    (attendance["hour"] == del_hour)
                )]
            attendance.to_csv("attendance.csv", index=False)
            st.success("Deleted successfully.")

    # ✅ CAMP RECORD MANAGEMENT
    if st.session_state.role in ["admin", "dept_admin"]:
        st.subheader("🛡 Camp Days Management")
        labels = students.apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1).tolist()
        s = st.selectbox("Select Student", labels)
        sid = s.split("(")[-1].replace(")", "")
        d1 = st.date_input("Camp Start")
        d2 = st.date_input("Camp End")
        act = st.selectbox("Activity", ["NSS", "NCC", "Club"])
        if st.button("Add Camp Record"):
            new = pd.DataFrame([{"student_id": sid, "start_date": pd.to_datetime(d1), "end_date": pd.to_datetime(d2), "activity": act}])
            camp_days = pd.concat([camp_days, new], ignore_index=True)
            camp_days.to_csv("camp_days.csv", index=False)
            st.success("Camp record added.")

        if not camp_days.empty:
            st.write("Existing Records")
            for i, row in camp_days.iterrows():
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.write(f"{row['student_id']} | {row['activity']} | {row['start_date'].date()} to {row['end_date'].date()}")
                with col2:
                    if st.button("Delete", key=f"del_camp_{i}"):
                        camp_days = camp_days.drop(i).reset_index(drop=True)
                        camp_days.to_csv("camp_days.csv", index=False)
                        st.experimental_rerun()

    # ✅ Reports section will be shared next (if required)

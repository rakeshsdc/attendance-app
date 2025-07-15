import streamlit as st
import pandas as pd
from datetime import datetime, date

st.set_page_config(page_title="FYUGP Attendance", layout="wide")

@st.cache_data
def load_data():
    students = pd.read_csv("students.csv")
    teachers = pd.read_csv("teachers.csv")
    courses = pd.read_csv("courses.csv")
    try:
        attendance = pd.read_csv("attendance.csv")
    except:
        attendance = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"])
    try:
        camp = pd.read_csv("camp_days.csv", parse_dates=["start_date", "end_date"])
    except:
        camp = pd.DataFrame(columns=["student_id", "start_date", "end_date", "activity"])
    return students, teachers, courses, attendance, camp

students, teachers, courses, attendance, camp_days = load_data()

# ---- SESSION ----
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.header("🔐 Login")
    email = st.sidebar.text_input("Email").strip().lower()
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        match = teachers[
            (teachers["email"].str.lower().str.strip() == email) &
            (teachers["password"].astype(str).str.strip() == password)
        ]
        if not match.empty:
            user = match.iloc[0]
            st.session_state.logged_in = True
            st.session_state.teacher_id = user["teacher_id"]
            st.session_state.teacher_name = user["name"]
            st.session_state.role = user["role"]
            st.session_state.department = user.get("department", "")
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials")
else:
    st.sidebar.write(f"👤 {st.session_state.teacher_name} ({st.session_state.role})")
    if st.sidebar.button("🚪 Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.title("📘 FYUGP Attendance Management")

    # ---- TAKE ATTENDANCE ----
    st.subheader("📝 Take Attendance")
    teacher_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
    if not teacher_courses.empty:
        selected_course = st.selectbox("Select Your Course", teacher_courses["course_id"])
        enrolled = students[
            (students["major_course"] == selected_course) |
            (students["minor1_course"] == selected_course) |
            (students["minor2_course"] == selected_course) |
            (students["mdc_course"] == selected_course) |
            (students["vac_course"] == selected_course)
        ]
        if enrolled.empty:
            st.warning("No students found.")
        else:
            sel_date = st.date_input("Select Date", value=date.today())
            existing = attendance[attendance["date"] == str(sel_date)]
            used_hours = existing["hour"].unique().tolist()
            hour_options = [str(h) for h in range(1, 7) if str(h) not in used_hours]
            hour_options.append("Extra Hour")
            sel_hour = st.selectbox("Select Hour", hour_options)
            extra_time = ""
            duration = ""
            if sel_hour == "Extra Hour":
                extra_time = st.time_input("Time")
                duration = st.number_input("Duration (minutes)", 10, 120)

            student_list = enrolled.apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1).tolist()
            absent = st.multiselect("Absent", student_list)
            nss = st.multiselect("NSS", student_list)
            ncc = st.multiselect("NCC", student_list)
            club = st.multiselect("Club", student_list)

            if st.button("✅ Submit Attendance"):
                recs = []
                for _, row in enrolled.iterrows():
                    label = f"{row['name']} ({row['student_id']})"
                    status = "P"
                    if label in absent: status = "A"
                    elif label in nss: status = "NSS"
                    elif label in ncc: status = "NCC"
                    elif label in club: status = "Club"
                    recs.append({
                        "date": str(sel_date), "hour": sel_hour, "course_id": selected_course,
                        "student_id": row["student_id"], "status": status,
                        "marked_by": st.session_state.teacher_id,
                        "extra_time": str(extra_time), "duration": duration
                    })
                attendance = attendance[~(
                    (attendance["date"] == str(sel_date)) &
                    (attendance["hour"] == sel_hour) &
                    (attendance["course_id"] == selected_course)
                )]
                attendance = pd.concat([attendance, pd.DataFrame(recs)], ignore_index=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("Attendance saved.")

    # ---- CAMP DAYS ----
    if st.session_state.role in ["admin", "dept_admin"]:
        st.subheader("🎪 Manage Camp Days")
        label_list = students.apply(lambda x: f"{x['name']} ({x['student_id']})", axis=1).tolist()
        s = st.selectbox("Select Student", label_list)
        sid = s.split("(")[-1].strip(")")
        d1 = st.date_input("Camp Start")
        d2 = st.date_input("Camp End")
        act = st.selectbox("Activity", ["NSS", "NCC", "Club"])
        if st.button("➕ Add Camp"):
            new = pd.DataFrame([{"student_id": sid, "start_date": d1, "end_date": d2, "activity": act}])
            camp_days = pd.concat([camp_days, new], ignore_index=True)
            camp_days.to_csv("camp_days.csv", index=False)
            st.success("Camp added.")
            st.rerun()
        st.write("📋 Existing Camp Records")
        for i, row in camp_days.iterrows():
            col1, col2 = st.columns([6, 1])
            with col1:
                st.write(f"{row['student_id']} - {row['activity']} ({row['start_date'].date()} → {row['end_date'].date()})")
            with col2:
                if st.button("🗑️ Delete", key=f"camp{i}"):
                    camp_days.drop(i, inplace=True)
                    camp_days.to_csv("camp_days.csv", index=False)
                    st.rerun()

    # ---- REPORTS ----
    st.subheader("📊 Reports")
    from_dt = st.date_input("From Date", value=date.today())
    to_dt = st.date_input("To Date", value=date.today())

    if st.session_state.role == "admin" or st.session_state.role == "dept_admin":
        dept = st.session_state.department
        dept_students = students[students["major_course"].str.startswith(dept[:3])]

        att = attendance.copy()
        att["date"] = pd.to_datetime(att["date"])
        att = att[(att["date"] >= pd.to_datetime(from_dt)) & (att["date"] <= pd.to_datetime(to_dt))]

        camp_filtered = []
        for _, row in camp_days.iterrows():
            s, e = row["start_date"], row["end_date"]
            dates = pd.date_range(s, e).strftime("%Y-%m-%d").tolist()
            camp_filtered.extend([(row["student_id"], d) for d in dates])
        camp_filtered = pd.DataFrame(camp_filtered, columns=["student_id", "date"])

        att_no_camp = att.copy()
        att_no_camp["is_camp"] = att_no_camp.apply(
            lambda x: (x["student_id"], x["date"].split(" ")[0]) in set([tuple(x) for x in camp_filtered.values]), axis=1
        )
        att_no_camp = att_no_camp[att_no_camp["is_camp"] == False]

        summary = att_no_camp.groupby("student_id")["status"].apply(lambda x: (x != "A").sum()).reset_index(name="attended")
        summary["total"] = att_no_camp.groupby("student_id")["status"].count().values
        summary["percent"] = (summary["attended"] / summary["total"] * 100).round(1)
        final = pd.merge(dept_students, summary, on="student_id", how="left").fillna(0)
        st.dataframe(final[["student_id", "name", "total", "attended", "percent"]])
        st.download_button("📥 Download Consolidated", final.to_csv(index=False), "consolidated.csv")

        detailed = att_no_camp[att_no_camp["student_id"].isin(dept_students["student_id"])]
        st.download_button("📥 Download Detailed Log", detailed.to_csv(index=False), "detailed.csv")

    elif st.session_state.role == "teacher":
        my_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]["course_id"].tolist()
        att = attendance[attendance["course_id"].isin(my_courses)]
        att["date"] = pd.to_datetime(att["date"])
        att = att[(att["date"] >= pd.to_datetime(from_dt)) & (att["date"] <= pd.to_datetime(to_dt))]

        for c in my_courses:
            st.write(f"📚 Course: {c}")
            cdata = att[att["course_id"] == c]
            summary = cdata.groupby("student_id")["status"].apply(lambda x: (x != "A").sum()).reset_index(name="attended")
            summary["total"] = cdata.groupby("student_id")["status"].count().values
            summary["percent"] = (summary["attended"] / summary["total"] * 100).round(1)
            merged = pd.merge(students, summary, on="student_id", how="inner")
            st.dataframe(merged[["student_id", "name", "total", "attended", "percent"]])
            st.download_button(f"📥 Download Consolidated - {c}", merged.to_csv(index=False), f"{c}_report.csv")

            st.download_button(f"📥 Detailed Log - {c}", cdata.to_csv(index=False), f"{c}_log.csv")

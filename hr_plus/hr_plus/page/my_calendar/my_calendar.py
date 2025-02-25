import frappe
from datetime import datetime, timedelta

@frappe.whitelist()
def get_calendar_events(start_date, end_date, employee=None, calendar_year=None):
    current_user = frappe.session.user
    hr_role = frappe.db.get_value('HR Plus Settings', None, 'hr_plus_role')
    is_hr_manager = frappe.db.exists('Has Role', {'parent': current_user, 'role': hr_role})

    filters = {'attendance_date': ['between', [start_date, end_date]], 'docstatus': 1}

    if not is_hr_manager:
        employee = frappe.db.get_value('Employee', {'user_id': current_user}, 'name')
        if not employee:
            return []
        filters['employee'] = employee

        holiday_list = frappe.db.get_value('Holiday List', {'name': calendar_year}, 'name')
    else:
        if employee:
            filters['employee'] = employee
           
        holiday_list = frappe.db.get_value('Holiday List', {'name': calendar_year}, 'name')

    weekly_off = frappe.db.get_value("Holiday List", {"name": holiday_list}, "weekly_off") if holiday_list else None

    #  Fetch Attendance Records
    events = frappe.db.get_list('Attendance', 
        filters=filters,
        fields=["name", "status", "in_time", "out_time", "attendance_date", "employee", 
                "attendance_request", "late_entry", "early_exit", "leave_type"]
    )
    
    attendance_map = {event["attendance_date"]: event for event in events}

    # Fetch Employee Checkin Records **only for dates where attendance is missing**
    checkin_records = frappe.db.get_list("Employee Checkin",
        filters={
            "time": ["between", [start_date, end_date]],
            "employee": employee
        }, 
        fields=["log_type", "time"]
    )

    # Process Check-in & Out Logic for missing attendance dates
    checkin_map = {}
    for checkin in checkin_records:
        checkin_datetime = checkin["time"]
        checkin_date = checkin_datetime.date()
        checkin_time = checkin_datetime.strftime("%H:%M")

        if checkin_date in attendance_map:
            continue

        if checkin_date not in checkin_map:
            checkin_map[checkin_date] = {"IN": None, "OUT": None}

        if checkin["log_type"] == "IN":
            if checkin_map[checkin_date]["IN"] is None or checkin_time < checkin_map[checkin_date]["IN"]:
                checkin_map[checkin_date]["IN"] = checkin_time
        elif checkin["log_type"] == "OUT":
            if checkin_map[checkin_date]["OUT"] is None or checkin_time > checkin_map[checkin_date]["OUT"]:
                checkin_map[checkin_date]["OUT"] = checkin_time

    # ✅ Add Check-in & Out records for missing attendance
    for date, times in checkin_map.items():
        in_time = times["IN"] if times["IN"] else "NA"
        out_time = times["OUT"] if times["OUT"] else "NA"

        events.append({
            'attendance_date': date,
            'status': 'Check-in & Out',
            'in_time': in_time,
            'out_time': out_time,
            'employee': employee,
            'name': None  
        })

    # ✅ Fetch Leave Application data for all statuses (Approved, Rejected, Pending)
    leave_data = frappe.db.get_list("Leave Application",
        filters={
            "employee": employee,
            "from_date": ["<=", end_date],
            "to_date": [">=", start_date],
            "docstatus": ["!=", 2]
        },
        fields=["name", "status", "from_date", "to_date", "leave_type"]
    )

    leave_map = {}
    for leave in leave_data:
        current_date = leave["from_date"]
        while current_date <= leave["to_date"]:
            leave_map[current_date] = {
                "status": leave["status"],
                "leave_type": leave["leave_type"],
                "leave_application": leave["name"]  # Store Leave Application ID
            }
            current_date += timedelta(days=1)

 

    # ✅ Ensure leave_application is always added to the events list

    for date, leave_details in leave_map.items():
        if date in attendance_map:
            # Update existing attendance record
            attendance_map[date]["status"] = "On Leave"
            attendance_map[date]["leave_status"] = leave_details["status"]
            attendance_map[date]["leave_type"] = leave_details["leave_type"]
            attendance_map[date]["leave_application"] = leave_details["leave_application"]  # ✅ Add Leave Application ID
            
            # ✅ If name is None, assign leave_application ID
            if not attendance_map[date].get("name"):
                attendance_map[date]["name"] = leave_details["leave_application"]  # ✅ Set name to Leave Application ID
        else:
            # If no attendance exists, create a new leave event
            events.append({
                'attendance_date': date,
                'status': 'On Leave',
                'leave_status': leave_details["status"],
                'leave_type': leave_details["leave_type"],
                'leave_application': leave_details["leave_application"],  # ✅ Include Leave Application ID
                'employee': employee,
                'name': leave_details["leave_application"]  # ✅ Assign Leave Application ID as name if no attendance record exists
            })


    # ✅ Process Final Events List
    modified_events = []
    for event in events:
        reason = ''
        workflow_state = ''
        if event.get('attendance_request'):
            reason = frappe.db.get_value('Attendance Request', event['attendance_request'], 'reason')
            workflow_state = frappe.db.get_value('Attendance Request', event['attendance_request'], 'workflow_state')

        event['reason'] = reason
        event['workflow_state'] = workflow_state

        if event.get('status') == 'Holiday':
            event['title'] = 'Holiday: ' + (event.get('public_holiday_') or '')

        modified_events.append(event)
        print(event.get('name'))
        print(event.get('leave_application'))
    return {
        "modified_events": modified_events,
        "weekly_off": weekly_off  
    }

    
@frappe.whitelist()
def is_hr_manager():
    current_user = frappe.session.user
    # Fetch the HR role from HR Plus Settings
    hr_role = frappe.db.get_value('HR Plus Settings', None, 'hr_plus_role')
    # Fetch the user's theme preference
    desk_theme = frappe.db.get_value('User', current_user, 'desk_theme')
    is_manager = frappe.db.exists('Has Role', {'parent': current_user, 'role': hr_role})
    # Return both HR manager status and desk theme
    return {
        'is_hr_manager': is_manager,
        'desk_theme': desk_theme
    }



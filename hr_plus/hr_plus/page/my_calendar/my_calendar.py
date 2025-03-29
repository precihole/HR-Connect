
import frappe
from datetime import datetime, timedelta

@frappe.whitelist()
def get_calendar_events(start_date, end_date, employee=None, calendar_year=None):
    current_user = frappe.session.user
    hr_role = frappe.db.get_value('HR Plus Settings', None, 'hr_plus_role')
    is_hr_manager = frappe.db.exists('Has Role', {'parent': current_user, 'role': hr_role})

    filters = {
        'attendance_date': ['between', [start_date, end_date]],
        'docstatus': 1
    }

    if not is_hr_manager:
        employee = frappe.db.get_value('Employee', {'user_id': current_user}, 'name')
        if not employee:
            return []
        filters['employee'] = employee
    if employee:
        filters['employee'] = employee

    holiday_list = frappe.db.get_value('Holiday List', {'name': calendar_year}, 'name')
    weekly_off = frappe.db.get_value("Holiday List", {"name": holiday_list}, "weekly_off") if holiday_list else None
    # ✅ Fetch Holiday Records
    events = []  # ✅ Initialize first before appending holidays

    # ✅ Fetch Holiday Records
    if holiday_list:
        holidays = frappe.db.get_list("Holiday",
            filters={
                "parent": calendar_year,
                "holiday_date": ["between", [start_date, end_date]],
                "weekly_off": 0
            },
            fields=["holiday_date", "description", "public_holiday_"],
            ignore_permissions=True 
        )

        for holiday in holidays:
            events.append({
                'attendance_date': holiday["holiday_date"],
                'status': 'Holiday',
                'public_holiday_': holiday.get("public_holiday_") or holiday.get("description"),
                'employee': employee,
                'name': f"Holiday-{holiday['holiday_date']}"
            })

    # ✅ Now fetch Attendance and append more to `events`
    attendance_records = frappe.db.get_list('Attendance', 
        filters=filters,
        fields=["name", "status", "in_time", "out_time", "attendance_date", "employee", 
                "attendance_request", "late_entry", "early_exit", "leave_type"]
    )
    events += attendance_records  # ✅ add attendance records to events

    # ✅ Fetch Attendance Records
    # events = frappe.db.get_list('Attendance', 
    #     filters=filters,
    #     fields=["name", "status", "in_time", "out_time", "attendance_date", "employee", 
    #             "attendance_request", "late_entry", "early_exit", "leave_type"]
    # )
    
    attendance_map = {event["attendance_date"]: event for event in events}

    # ✅ Fetch Leave Application Data
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
                "leave_application": leave["name"]
            }
            current_date += timedelta(days=1)

    # ✅ Fetch Attendance Request Data (NEW)
    attendance_requests = frappe.db.get_list("Attendance Request",
        filters={
            "employee": employee,
            "from_date": ["<=", end_date],
            "to_date": [">=", start_date],
            "docstatus": ["!=", 2]
        },
        fields=["name", "workflow_state", "from_date", "to_date", "custom_from_time", "custom_to_time", "reason"]
    )

    attendance_request_map = {}
    for request in attendance_requests:
        current_date = request["from_date"]
        while current_date <= request["to_date"]:
            attendance_request_map[current_date] = {
                "workflow_state": request["workflow_state"],
                "from_time": request["custom_from_time"],
                "to_time": request["custom_to_time"],
                "reason": request["reason"],
                "attendance_request": request["name"]
            }
            current_date += timedelta(days=1)

    # ✅ Add Leave Applications to Events
    for date, leave_details in leave_map.items():
        if date in attendance_map:
            attendance_map[date]["status"] = "On Leave"
            attendance_map[date]["leave_status"] = leave_details["status"]
            attendance_map[date]["leave_type"] = leave_details["leave_type"]
            attendance_map[date]["leave_application"] = leave_details["leave_application"]

            if not attendance_map[date].get("name"):
                attendance_map[date]["name"] = leave_details["leave_application"]
        else:
            events.append({
                'attendance_date': date,
                'status': 'On Leave',
                'leave_status': leave_details["status"],
                'leave_type': leave_details["leave_type"],
                'leave_application': leave_details["leave_application"],
                'employee': employee,
                'name': leave_details["leave_application"]
            })

    # ✅ Add Attendance Requests to Events (ONLY IF NO ATTENDANCE EXISTS)
    for date, request_details in attendance_request_map.items():
        if date not in attendance_map:  # ✅ Show Attendance Request ONLY if no Attendance exists
            events.append({
                'attendance_date': date,
                'status': 'Attendance Request',
                'workflow_state': request_details["workflow_state"],
                'from_time': request_details["from_time"],
                'to_time': request_details["to_time"],
                'reason': request_details["reason"],
                'attendance_request': request_details["attendance_request"],
                'employee': employee,
                'name': request_details["attendance_request"]
            })

    # ✅ Process Final Events List
    modified_events = []
    for event in events:
        if event.get('attendance_request'):
            reason = frappe.db.get_value('Attendance Request', event['attendance_request'], 'reason')
            workflow_state = frappe.db.get_value('Attendance Request', event['attendance_request'], 'workflow_state')
            event['reason'] = reason
            event['workflow_state'] = workflow_state

        modified_events.append(event)

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



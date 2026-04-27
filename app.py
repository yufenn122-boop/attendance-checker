import streamlit as st
import requests
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

# =========================
# 1. 基础配置
# =========================

# 建议后面放到 Streamlit Secrets 里
APP_ID = "cli_a965b2078cf99bde"
APP_SECRET = "gcmlnizhUdZvI8HVPuWuqdnpmvD3Latq"

APP_TOKEN = "Djscb2AQfaLXdtsszqTcT7JMnpb"
TABLE_ID = "tbl4WiEUD7H8z5na"

NAME_FIELD = "群昵称"
TIME_FIELD = "提交时间"

TIMEZONE = ZoneInfo("Asia/Shanghai")

# 全部学员名单
ALL_STUDENTS = [
    "用户309316",
    "用户833314",
    "用户385173",
    "用户417845",
]

# 学员昵称对应
STUDENT_NICKNAMES = {
    "用户309316": "公主",
    "用户833314": "escape",
    "用户385173": "十六星",
    "用户417845": "beyourself",
}


# =========================
# 2. 页面基础设置
# =========================

st.set_page_config(
    page_title="谁没有做任务",
    page_icon="✅",
    layout="centered"
)


# =========================
# 3. 获取飞书 tenant_access_token
# =========================

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

    payload = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }

    resp = requests.post(url, json=payload, timeout=20)
    data = resp.json()

    if data.get("code") != 0:
        raise Exception(f"获取 tenant_access_token 失败：{data}")

    return data["tenant_access_token"]


# =========================
# 4. 读取飞书多维表格记录
# =========================

def fetch_records(token):
    url = (
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/"
        f"{APP_TOKEN}/tables/{TABLE_ID}/records/search"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    all_records = []
    page_token = None

    while True:
        params = {
            "page_size": 500
        }

        if page_token:
            params["page_token"] = page_token

        body = {
            "page_size": 500
        }

        resp = requests.post(
            url,
            headers=headers,
            params=params,
            json=body,
            timeout=30
        )

        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"读取多维表格失败：{data}")

        items = data.get("data", {}).get("items", [])
        all_records.extend(items)

        has_more = data.get("data", {}).get("has_more", False)
        page_token = data.get("data", {}).get("page_token")

        if not has_more:
            break

    return all_records


# =========================
# 5. 解析飞书时间字段
# =========================

def parse_feishu_time(value):
    """
    兼容飞书常见时间格式：
    1. 毫秒时间戳
    2. 秒级时间戳
    3. 字符串时间
    """

    if value is None:
        return None

    if isinstance(value, int):
        if value > 10_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=TIMEZONE)
        return datetime.fromtimestamp(value, tz=TIMEZONE)

    if isinstance(value, float):
        if value > 10_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=TIMEZONE)
        return datetime.fromtimestamp(value, tz=TIMEZONE)

    if isinstance(value, str):
        value = value.strip()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=TIMEZONE)
            except ValueError:
                continue

    return None


# =========================
# 6. 解析学员姓名字段
# =========================

def parse_name(value):
    """
    兼容：
    1. 普通文本：用户833314
    2. 飞书人员字段：[{"name": "..."}]
    """

    if value is None:
        return None

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list) and len(value) > 0:
        first = value[0]
        if isinstance(first, dict):
            return (
                first.get("name")
                or first.get("en_name")
                or first.get("nickname")
                or ""
            ).strip()

    if isinstance(value, dict):
        return (
            value.get("name")
            or value.get("en_name")
            or value.get("nickname")
            or ""
        ).strip()

    return str(value).strip()


# =========================
# 7. 名字显示格式
# =========================

def display_student_name(student):
    nickname = STUDENT_NICKNAMES.get(student, "")
    if nickname:
        return f"{student}（{nickname}）"
    return student


# =========================
# 8. 生成最近三天的检查窗口
# =========================

def build_check_windows():
    """
    检查逻辑：

    检查日 = 今天 / 昨天 / 前天

    每一个检查日的窗口：
    前一天 00:00 ～ 检查日 10:00

    例如今天是 4.27：
    今天窗口：4.26 00:00 ～ 4.27 10:00
    昨天窗口：4.25 00:00 ～ 4.26 10:00
    前天窗口：4.24 00:00 ～ 4.25 10:00
    """

    now = datetime.now(TIMEZONE)
    today = now.date()

    check_days = [
        today - timedelta(days=2),
        today - timedelta(days=1),
        today,
    ]

    windows = []

    for check_day in check_days:
        start_date = check_day - timedelta(days=1)

        start_dt = datetime.combine(
            start_date,
            time(0, 0, 0),
            tzinfo=TIMEZONE
        )

        end_dt = datetime.combine(
            check_day,
            time(10, 0, 0),
            tzinfo=TIMEZONE
        )

        windows.append({
            "check_day": check_day,
            "start_dt": start_dt,
            "end_dt": end_dt,
        })

    return windows


# =========================
# 9. 核心检查逻辑
# =========================

def check_attendance():
    token = get_tenant_access_token()
    records = fetch_records(token)

    windows = build_check_windows()

    # 每个学生在每个检查日是否完成
    student_status = {
        student: {}
        for student in ALL_STUDENTS
    }

    for student in ALL_STUDENTS:
        for window in windows:
            student_status[student][window["check_day"]] = False

    valid_records = []

    for record in records:
        fields = record.get("fields", {})

        raw_name = fields.get(NAME_FIELD)
        raw_time = fields.get(TIME_FIELD)

        name = parse_name(raw_name)
        submit_time = parse_feishu_time(raw_time)

        if not name or not submit_time:
            continue

        if name not in student_status:
            continue

        for window in windows:
            check_day = window["check_day"]
            start_dt = window["start_dt"]
            end_dt = window["end_dt"]

            if start_dt <= submit_time <= end_dt:
                student_status[name][check_day] = True

                valid_records.append({
                    "学员": name,
                    "昵称": STUDENT_NICKNAMES.get(name, ""),
                    "归属检查日": check_day.strftime("%Y-%m-%d"),
                    "窗口开始": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "窗口结束": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "实际提交时间": submit_time.strftime("%Y-%m-%d %H:%M:%S"),
                })

    missing_summary = []

    for student in ALL_STUDENTS:
        missing_days = []

        for window in windows:
            check_day = window["check_day"]
            is_done = student_status[student].get(check_day, False)

            if not is_done:
                missing_days.append(check_day)

        if missing_days:
            missing_summary.append({
                "学员": student,
                "昵称": STUDENT_NICKNAMES.get(student, ""),
                "缺卡天数": len(missing_days),
                "缺卡日期": "、".join([d.strftime("%Y-%m-%d") for d in missing_days]),
                "缺卡日期列表": missing_days,
            })

    today = datetime.now(TIMEZONE).date()

    today_missing_students = []
    today_checked_students = []

    for student in ALL_STUDENTS:
        if student_status[student].get(today, False):
            today_checked_students.append(student)
        else:
            today_missing_students.append(student)

    return {
        "windows": windows,
        "student_status": student_status,
        "missing_summary": missing_summary,
        "today_checked_students": today_checked_students,
        "today_missing_students": today_missing_students,
        "valid_records": valid_records,
        "total_records": len(records),
    }


# =========================
# 10. 页面显示
# =========================

st.title("✅ 谁没有做任务")
st.caption("自动检查飞书多维表格打卡记录")

st.divider()

st.write("### 检查规则")

st.info("每一天的检查窗口：前一天 00:00 ～ 当天 10:00")

st.write("例如今天是 4.27：")

st.code(
    "今天检查：4.26 00:00 ～ 4.27 10:00\n"
    "昨天检查：4.25 00:00 ～ 4.26 10:00\n"
    "前天检查：4.24 00:00 ～ 4.25 10:00"
)

st.write("### 当前学员名单")

for student in ALL_STUDENTS:
    st.write(f"- {display_student_name(student)}")

st.divider()

if st.button("开始检查", type="primary"):
    with st.spinner("正在读取飞书多维表格..."):
        try:
            result = check_attendance()

            st.success("检查完成")

            st.write("### 本次检查窗口")

            for window in result["windows"]:
                st.write(
                    f"- {window['check_day'].strftime('%Y-%m-%d')}："
                    f"{window['start_dt'].strftime('%Y-%m-%d %H:%M:%S')} "
                    f"～ "
                    f"{window['end_dt'].strftime('%Y-%m-%d %H:%M:%S')}"
                )

            st.divider()

            col1, col2, col3 = st.columns(3)
            col1.metric("全员人数", len(ALL_STUDENTS))
            col2.metric("今日已打卡", len(result["today_checked_students"]))
            col3.metric("今日未打卡", len(result["today_missing_students"]))

            st.divider()

            st.write("### 缺卡提醒")

            if result["missing_summary"]:
                for item in result["missing_summary"]:
                    student = item["学员"]
                    days = item["缺卡天数"]
                    dates = item["缺卡日期"]
                    name = display_student_name(student)

                    if days >= 3:
                        st.error(f"{name} 已连续缺卡，需要一次性补打三天：{dates}")
                    elif days == 2:
                        st.warning(f"{name} 缺卡 2 天，需要补打：{dates}")
                    else:
                        st.info(f"{name} 缺卡 1 天：{dates}")
            else:
                st.success("最近三天全部学员都已完成打卡 🎉")

            with st.expander("查看今日未打卡名单"):
                if result["today_missing_students"]:
                    for student in result["today_missing_students"]:
                        st.write(f"- {display_student_name(student)}")
                else:
                    st.write("今日全部已打卡")

            with st.expander("查看每个学员最近三天状态"):
                status_rows = []

                for student in ALL_STUDENTS:
                    row = {
                        "学员": student,
                        "昵称": STUDENT_NICKNAMES.get(student, ""),
                    }

                    for window in result["windows"]:
                        check_day = window["check_day"]
                        is_done = result["student_status"][student].get(check_day, False)

                        row[check_day.strftime("%Y-%m-%d")] = "已打卡" if is_done else "未打卡"

                    status_rows.append(row)

                st.dataframe(status_rows, use_container_width=True)

            with st.expander("查看匹配到的有效提交记录"):
                if result["valid_records"]:
                    st.dataframe(result["valid_records"], use_container_width=True)
                else:
                    st.write("最近三个检查窗口内没有匹配到有效提交记录")

            with st.expander("调试信息"):
                st.write(f"飞书表格总读取记录数：{result['total_records']}")

        except Exception as e:
            st.error("检查失败")
            st.exception(e)

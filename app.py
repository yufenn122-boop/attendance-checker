import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# =========================
# 1. 基础配置
# =========================

APP_ID = "cli_a965b2078cf99bde"
APP_SECRET = "gcmlnizhUdZvI8HVPuWuqdnpmvD3Latq"

APP_TOKEN = "Djscb2AQfaLXdtsszqTcT7JMnpb"
TABLE_ID = "tbl4WiEUD7H8z5na"

NAME_FIELD = "群昵称"
TIME_FIELD = "提交时间"

# 这里写死全部学员名单
ALL_STUDENTS = [
    "用户309316",
    "用户833314",
    "用户385173",
    "用户417845",
]

STUDENT_NICKNAMES = {
    "用户309316": "公主",
    "用户833314": "escape",
    "用户385173": "十六星",
    "用户417845": "beyourself",
}

TIMEZONE = ZoneInfo("Asia/Shanghai")


# =========================
# 2. 获取飞书 token
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
# 3. 读取飞书多维表格记录
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

        resp = requests.post(url, headers=headers, params=params, json=body, timeout=30)
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
# 4. 解析飞书时间字段
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

    # 飞书日期字段常见：毫秒时间戳
    if isinstance(value, int):
        if value > 10_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=TIMEZONE)
        else:
            return datetime.fromtimestamp(value, tz=TIMEZONE)

    if isinstance(value, float):
        if value > 10_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=TIMEZONE)
        else:
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
# 5. 解析飞书人员字段 / 文本字段
# =========================

def parse_name(value):
    """
    兼容：
    1. 普通文本：用户833314
    2. 飞书人员字段：[{"name": "...", "en_name": "..."}]
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
# 6. 检查未打卡
# =========================

def check_attendance():
    now = datetime.now(TIMEZONE)

    today_10 = now.replace(hour=10, minute=0, second=0, microsecond=0)
    yesterday_0 = (today_10 - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    token = get_tenant_access_token()
    records = fetch_records(token)

    checked_students = set()
    valid_records = []

    for record in records:
        fields = record.get("fields", {})

        raw_name = fields.get(NAME_FIELD)
        raw_time = fields.get(TIME_FIELD)

        name = parse_name(raw_name)
        submit_time = parse_feishu_time(raw_time)

        if not name or not submit_time:
            continue

        if yesterday_0 <= submit_time <= today_10:
            checked_students.add(name)
            valid_records.append({
                "学员": name,
                "提交时间": submit_time.strftime("%Y-%m-%d %H:%M:%S")
            })

    all_students = set([s.strip() for s in ALL_STUDENTS if s.strip()])
    missing_students = sorted(all_students - checked_students)

    return {
        "start_time": yesterday_0,
        "end_time": today_10,
        "all_students": sorted(all_students),
        "checked_students": sorted(checked_students),
        "missing_students": missing_students,
        "valid_records": valid_records,
        "total_records": len(records),
    }


# =========================
# 7. Streamlit 页面
# =========================

st.set_page_config(
    page_title="谁没有做任务",
    page_icon="✅",
    layout="centered"
)

st.title("✅ 谁没有做任务")
st.caption("自动检查飞书多维表格打卡记录")

st.divider()

st.write("检查规则：")

st.code("昨天 00:00 ～ 今天 10:00")

st.write("当前学员名单：")

for student in ALL_STUDENTS:
    nickname = STUDENT_NICKNAMES.get(student, "")
    if nickname:
        st.write(f"- {student}（{nickname}）")
    else:
        st.write(f"- {student}")

st.divider()

if st.button("开始检查", type="primary"):
    with st.spinner("正在读取飞书多维表格..."):
        try:
            result = check_attendance()

            st.success("检查完成")

            st.write("### 检查时间段")
            st.write(
                f"{result['start_time'].strftime('%Y-%m-%d %H:%M:%S')} "
                f"～ "
                f"{result['end_time'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("全员人数", len(result["all_students"]))
            col2.metric("已打卡人数", len(result["checked_students"]))
            col3.metric("未打卡人数", len(result["missing_students"]))

            st.divider()

            if result["missing_students"]:
                st.error("以下学员未完成打卡：")
                for name in result["missing_students"]:
                    nickname = STUDENT_NICKNAMES.get(name, "")
                    if nickname:
                        st.write(f"- {name}（{nickname}）")
                    else:
                        st.write(f"- {name}")
            else:
                st.success("全部学员已完成打卡 🎉")

            with st.expander("查看已打卡名单"):
                for name in result["checked_students"]:
                    nickname = STUDENT_NICKNAMES.get(name, "")
                    if nickname:
                        st.write(f"- {name}（{nickname}）")
                    else:
                        st.write(f"- {name}")

            with st.expander("查看有效提交记录"):
                if result["valid_records"]:
                    st.dataframe(result["valid_records"], use_container_width=True)
                else:
                    st.write("当前时间段内没有有效提交记录")

            with st.expander("调试信息"):
                st.write(f"飞书表格总读取记录数：{result['total_records']}")

        except Exception as e:
            st.error("检查失败")
            st.exception(e)

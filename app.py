import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import altair as alt

# ===== ページ設定 =====
st.set_page_config(page_title="通所日報ダッシュボード", layout="wide")
st.title("📝 通所日報ダッシュボード")

# ===== Google 認証 =====
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=scope
)
client = gspread.authorize(credentials)

# ===== スプレッドシートを開く =====
sheet_url = "https://docs.google.com/spreadsheets/d/1v4rNnnwxUcSN_O2QjZhHowVGyVclrWlYo8w8yRdd89w/edit"
spreadsheet = client.open_by_url(sheet_url)

worksheet_form = spreadsheet.worksheet("フォームの回答 1")
records_form = worksheet_form.get_all_records()
df_form = pd.DataFrame(records_form)

worksheet_map = spreadsheet.worksheet("一覧")
records_map = worksheet_map.get_all_records()
df_map = pd.DataFrame(records_map)

# ===== データ前処理 =====
df_form.rename(columns={
    df_form.columns[0]: "Timestamp",
    df_form.columns[1]: "Email",
}, inplace=True)
df_map.columns = ["Email", "Name"]

df = pd.merge(df_form, df_map, on="Email", how="left")

df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df["Timestamp_str"] = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
df["Date"] = df["Timestamp"].dt.strftime("%Y-%m-%d")
df["YearMonth"] = df["Timestamp"].dt.strftime("%Y-%m")
df["Weekday"] = df["Timestamp"].dt.day_name()

# ✅ 起床・就寝時間を柔軟にパース
def parse_time(val):
    try:
        if isinstance(val, str):
            return pd.to_datetime(val, format="%H:%M:%S", errors="coerce")
        elif isinstance(val, (int, float)):
            return pd.to_datetime("1899-12-30") + pd.to_timedelta(val, unit="D")
        else:
            return pd.NaT
    except:
        return pd.NaT

df["起床時間_dt"] = df["起床時間"].apply(parse_time)
df["就寝時間_dt"] = df["就寝時間"].apply(parse_time)

df["睡眠時間_h"] = (df["起床時間_dt"] - df["就寝時間_dt"]).dt.total_seconds() / 3600
df.loc[df["睡眠時間_h"] < 0, "睡眠時間_h"] += 24

# === 不要列
columns_to_hide = ["名"]
df = df.drop(columns=[col for col in columns_to_hide if col in df.columns])

cols = df.columns.tolist()
for col in ["Timestamp_str", "Name", "Email", "Timestamp"]:
    if col in cols:
        cols.remove(col)
new_order = ["Timestamp_str", "Name"] + cols + ["Email", "Timestamp"]
df = df[new_order]

# ===== UI =====
mode = st.radio(
    "表示モードを選択",
    ["📅 日付別（全員）", "👤 利用者別（月別）", "📊 人ごと分析"],
    horizontal=True
)

if mode == "📅 日付別（全員）":
    sel_date = st.date_input("表示する日付", value=pd.Timestamp.today().date())
    daily_df = df[df["Date"] == sel_date.strftime("%Y-%m-%d")]
    daily_df = daily_df.sort_values("Timestamp", ascending=True)
    display_df = daily_df.drop(columns=["Timestamp"])

    st.subheader(f"📅 {sel_date} の日報（{len(display_df)} 件）")

    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_default_column(editable=False)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", pinned="left")
    gridOptions = gb.build()

    AgGrid(
        display_df,
        gridOptions=gridOptions,
        height=600,
        enable_enterprise_modules=True,
    )

elif mode == "👤 利用者別（月別）":
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("利用者を選択", names)
    sel_month = st.selectbox(
        "表示する月",
        sorted(df["YearMonth"].dropna().unique())
    )

    user_df = df[(df["Name"] == sel_name) & (df["YearMonth"] == sel_month)]
    user_df = user_df.sort_values("Timestamp", ascending=True)
    display_user_df = user_df.drop(columns=["Timestamp"])

    st.subheader(f"👤 {sel_name} の {sel_month} の日報（{len(display_user_df)} 件）")

    gb = GridOptionsBuilder.from_dataframe(display_user_df)
    gb.configure_default_column(editable=False)
    gb.configure_column("Timestamp_str", header_name="Timestamp", pinned="left")
    gb.configure_column("Name", pinned="left")
    gridOptions = gb.build()

    AgGrid(
        display_user_df,
        gridOptions=gridOptions,
        height=600,
        enable_enterprise_modules=True,
    )

else:
    names = sorted(df["Name"].dropna().unique())
    sel_name = st.selectbox("分析対象を選択", names)
    person_df = df[df["Name"] == sel_name].copy()

    st.subheader(f"📊 {sel_name} の日報分析")

    st.markdown("### 📅 月ごとの通所回数")
    month_counts = person_df.groupby("YearMonth").size().reset_index(name="Count")
    st.bar_chart(month_counts.set_index("YearMonth"))

    st.markdown("### 📅 曜日別の出席傾向")
    weekday_counts = (
        person_df.groupby(["YearMonth", "Weekday"])
        .size()
        .reset_index(name="Count")
    )
    heatmap = alt.Chart(weekday_counts).mark_rect().encode(
        x=alt.X('Weekday:N', sort=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]),
        y='YearMonth:N',
        color='Count:Q'
    )
    st.altair_chart(heatmap, use_container_width=True)

    st.markdown("### ⏰ 起床・就寝時間 平均とばらつき")

    def sec2hm(s):
        if pd.isna(s):
            return "データなし"
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        return f"{h:02}:{m:02}"

    # ✅ 起床時間（秒）
    valid_wakeup = person_df["起床時間_dt"].dropna()
    wakeup_sec = valid_wakeup.dt.hour * 3600 + valid_wakeup.dt.minute * 60 + valid_wakeup.dt.second

    # ✅ 就寝時間（秒） ← 日付は無視して時間だけで計算
    valid_bed = person_df["就寝時間_dt"].dropna()
    bed_sec = valid_bed.dt.hour * 3600 + valid_bed.dt.minute * 60 + valid_bed.dt.second
    # 💡 注意: 23:00 など深夜時間はそのまま秒で扱う

    wakeup_mean_sec = wakeup_sec.mean()
    wakeup_std_sec = wakeup_sec.std()
    bed_mean_sec = bed_sec.mean()
    bed_std_sec = bed_sec.std()

    def sec2hm(s):
        if pd.isna(s):
            return "データなし"
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        return f"{h:02}:{m:02}"

    st.metric("平均起床時間", sec2hm(wakeup_mean_sec))
    st.metric("起床時間のばらつき (分)", f"{wakeup_std_sec/60:.1f}" if pd.notna(wakeup_std_sec) else "データなし")

    st.metric("平均就寝時間", sec2hm(bed_mean_sec))
    st.metric("就寝時間のばらつき (分)", f"{bed_std_sec/60:.1f}" if pd.notna(bed_std_sec) else "データなし")

    st.markdown("### 💤 睡眠時間の推移")
    sleep_df = person_df[["Date", "睡眠時間_h"]].dropna().drop_duplicates("Date")
    st.line_chart(sleep_df.set_index("Date"))

    st.markdown("### 🎯 目標・課題 WordCloud")
    texts = (
        person_df["今日の目標"].dropna().tolist()
        + person_df["課題の対処はどうしますか？"].dropna().tolist()
    )
    text_all = " ".join(texts)

    if text_all.strip():
        wc = WordCloud(
            background_color="white",
            font_path="/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            width=800,
            height=400
        ).generate(text_all)
        fig, ax = plt.subplots()
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    else:
        st.info("データが不足しています。")

    st.markdown("### 🌙 オフタイム自己管理度の推移")
    off_cols = [
        "オフタイムコントロール [睡眠]",
        "オフタイムコントロール [食事]",
        "オフタイムコントロール [ストレス]",
    ]
    off_map = {"〇": 2, "△": 1, "✕": 0}
    for col in off_cols:
        person_df[col] = person_df[col].map(off_map)

    off_df = person_df[["Date"] + off_cols].dropna()
    off_df = off_df.groupby("Date")[off_cols].mean().reset_index()
    st.line_chart(off_df.set_index("Date"))

    st.markdown("### 📌 相談・連絡（『なし』以外）")
    contact_df = person_df[
        person_df["相談・連絡"].notna() & (person_df["相談・連絡"] != "なし")
    ]
    st.dataframe(contact_df[["Date", "相談・連絡"]])

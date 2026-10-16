from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Coffee Shop Sales", layout="wide")
st.title("Dashboard Coffee Shop Sales")
st.caption(
    "Januari–Juni 2023. Mata data belum dinyatakan pada file."
)

folder = Path(__file__).resolve().parent
file_data = folder / "data_prepared" / "coffee_sales_prepared.csv"


@st.cache_data
def load_data(path, modified_time):
    data = pd.read_csv(path)
    data["transaction_date"] = pd.to_datetime(data["transaction_date"])
    return data


if not file_data.exists():
    st.error(
        "Jalankan audit terlebih dahulu. File coffee_sales_prepared.csv belum ada."
    )
    st.stop()

df = load_data(str(file_data), file_data.stat().st_mtime_ns)

# Filter gerai, kategori, dan tanggal berlaku untuk seluruh grafik dan indikator.
st.sidebar.header("Filter data")
stores = sorted(df["store_location"].unique().tolist())
selected = st.sidebar.multiselect(
    "Pilih gerai",
    options=stores,
    default=stores,
)
categories = sorted(df["product_category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Pilih kategori produk",
    options=categories,
    default=categories,
)
min_date = df["transaction_date"].min().date()
max_date = df["transaction_date"].max().date()
selected_dates = st.sidebar.date_input(
    "Pilih rentang tanggal",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if not selected or not selected_categories:
    st.info("Pilih minimal satu gerai dan satu kategori produk.")
    st.stop()
if len(selected_dates) != 2:
    st.info("Pilih tanggal mulai dan tanggal akhir.")
    st.stop()

start_date, end_date = selected_dates
if start_date > end_date:
    st.info("Tanggal mulai harus sebelum atau sama dengan tanggal akhir.")
    st.stop()

data_filter = df[
    df["store_location"].isin(selected)
    & df["product_category"].isin(selected_categories)
    & df["transaction_date"].dt.date.between(start_date, end_date)
].copy()
if data_filter.empty:
    st.info("Tidak ada transaksi untuk kombinasi filter yang dipilih.")
    st.stop()
st.sidebar.caption(
    "Semua grafik mengikuti pilihan gerai, kategori produk, dan tanggal."
)

# Bulan selalu mengikuti cakupan sumber, termasuk bulan tanpa catatan.
months = pd.period_range(
    data_filter["transaction_date"].min().to_period("M"),
    data_filter["transaction_date"].max().to_period("M"),
    freq="M",
)
monthly = (
    data_filter.groupby("month")
    .agg(
        total_sales=("sales", "sum"),
        total_transactions=("transaction_id", "nunique"),
        total_units=("transaction_qty", "sum"),
    )
    .reindex(months.astype(str), fill_value=0)
)
previous = monthly["total_sales"].shift(1)
monthly["growth_pct"] = (
    (monthly["total_sales"] - previous) / previous * 100
).where(previous.ne(0) & previous.notna())

monthly["average_transaction_value"] = (
    monthly["total_sales"] / monthly["total_transactions"].replace(0, pd.NA)
)
monthly = monthly.reset_index(names="month")

def format_angka(value, decimals=2):
    return (
        f"{value:,.{decimals}f}"
        .replace(",", "_")
        .replace(".", ",")
        .replace("_", ".")
    )


total_sales = data_filter["sales"].sum()
total_transactions = data_filter["transaction_id"].nunique()
average = (
    total_sales / total_transactions if total_transactions else None
)
growth = (
    monthly["growth_pct"].iloc[-1]
    if len(monthly) and pd.notna(monthly["growth_pct"].iloc[-1])
    else None
)
last_month = pd.Period(months[-1], freq="M")
st.subheader("Ringkasan penjualan")
st.caption(
    f"Total, transaksi, dan rata-rata: seluruh periode. "
    f"Pertumbuhan: {last_month} terhadap {last_month - 1}."
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total penjualan", format_angka(total_sales))
col2.metric("Transaksi tercatat", format_angka(total_transactions, 0))
col3.metric(
    "Rata-rata nilai transaksi",
    format_angka(average) if average is not None else "Belum tersedia",
)
col4.metric(
    f"Pertumbuhan bulan {last_month}",
    f"{format_angka(growth)}%" if growth is not None else "Belum tersedia",
)

st.subheader("Tren penjualan bulanan")
fig = px.line(
    monthly,
    x="month",
    y="total_sales",
    markers=True,
    labels={
        "month": "Bulan",
        "total_sales": "Nilai penjualan",
    },
    title="Penjualan bulanan",
)
fig.update_traces(line_color="#0B7A5A", fill="tozeroy")
fig.update_layout(
    xaxis_title="Bulan",
    yaxis_title="Nilai penjualan",
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True, key="trend")

table = monthly.rename(
    columns={
        "month": "Bulan",
        "total_sales": "Total penjualan",
        "total_transactions": "Transaksi tercatat",
        "total_units": "Unit terjual",
        "growth_pct": "Pertumbuhan (%)",
        "average_transaction_value": "Rata-rata nilai transaksi",
    }
)
st.dataframe(
    table.style.format(
        {
            "Total penjualan": "{:,.2f}",
            "Transaksi tercatat": "{:,.0f}",
            "Unit terjual": "{:,.0f}",
            "Pertumbuhan (%)": "{:,.2f}",
            "Rata-rata nilai transaksi": "{:,.2f}",
        },
        na_rep="Belum tersedia",
        decimal=",",
        thousands=".",
    ),
    use_container_width=True,
)

st.divider()
st.header("Perbandingan gerai dan kategori")
left, right = st.columns(2)

with left:
    st.subheader("Penjualan per gerai")
    sales_by_store = (
        data_filter.groupby("store_location", as_index=False)
        .agg(total_sales=("sales", "sum"))
        .sort_values("total_sales", ascending=False)
    )
    fig_store = px.bar(
        sales_by_store,
        x="store_location",
        y="total_sales",
        color="store_location",
        text_auto=".2s",
        labels={
            "store_location": "Gerai",
            "total_sales": "Nilai penjualan",
        },
    )
    fig_store.update_layout(
        showlegend=False,
        height=400,
        xaxis_title="Gerai",
        yaxis_title="Nilai penjualan",
    )
    st.plotly_chart(
        fig_store,
        use_container_width=True,
        key="stores",
    )
    st.caption("Gerai mengikuti pilihan filter gerai dan kategori produk.")

with right:
    st.subheader("Kontribusi penjualan kategori")
    sales_by_category = (
        data_filter.groupby("product_category", as_index=False)
        .agg(total_sales=("sales", "sum"))
        .sort_values("total_sales", ascending=False)
    )
    fig_category = px.pie(
        sales_by_category,
        names="product_category",
        values="total_sales",
        hole=0.55,
    )
    fig_category.update_traces(
        textinfo="label+percent",
        hovertemplate="%{label}<br>Kontribusi: %{percent}<extra></extra>",
    )
    fig_category.update_layout(
        height=400,
        legend_title_text="Kategori",
    )
    st.plotly_chart(
        fig_category,
        use_container_width=True,
        key="categories",
    )
    st.caption(
        "Kontribusi terhadap total dalam pilihan gerai dan kategori yang sama."
    )

st.header("Produk dan pola waktu transaksi")
left, right = st.columns(2)

with left:
    st.subheader("10 produk dengan penjualan tertinggi")
    top_products = (
        data_filter.groupby(
            ["product_id", "product_detail"], as_index=False
        )
        .agg(total_sales=("sales", "sum"))
        .sort_values("total_sales", ascending=False)
        .head(10)
    )
    top_products["label"] = (
        top_products["product_detail"].astype(str)
        + " ("
        + top_products["product_id"].astype(str)
        + ")"
    )
    fig_products = px.bar(
        top_products,
        x="total_sales",
        y="label",
        orientation="h",
        color="total_sales",
        labels={
            "label": "Produk",
            "total_sales": "Nilai penjualan",
        },
    )
    fig_products.update_layout(
        height=470,
        yaxis={"categoryorder": "total ascending"},
    )
    st.plotly_chart(
        fig_products,
        use_container_width=True,
        key="products",
    )
    st.caption(
        "Produk dengan nilai penjualan tertinggi; bukan jumlah unit atau keuntungan."
    )

with right:
    st.subheader("Transaksi tercatat menurut jam")
    by_hour = (
        data_filter.groupby("hour", as_index=False)
        .agg(total_transactions=("transaction_id", "nunique"))
        .sort_values("hour")
    )
    by_hour["label"] = (
        by_hour["hour"].astype(int).astype(str).str.zfill(2) + ":00"
    )
    fig_hour = px.bar(
        by_hour,
        x="label",
        y="total_transactions",
        color="total_transactions",
        labels={
            "label": "Jam",
            "total_transactions": "Transaksi tercatat",
        },
    )
    fig_hour.update_layout(
        height=470,
        xaxis_title="Jam",
        yaxis_title="Transaksi tercatat",
    )
    st.plotly_chart(
        fig_hour,
        use_container_width=True,
        key="hours",
    )
    st.caption(
        "Akumulasi sepanjang periode, belum mengukur tren antar layanan."
    )

st.caption(
    "Transaksi tercatat adalah transaction_id unik, bukan pelanggan unik. "
    "Rata-rata nilai belum dipastikan sebagai seluruh isi struk pelanggan."
)

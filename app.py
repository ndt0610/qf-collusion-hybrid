"""Local, read-only presentation of the locked QF research artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from qf_hybrid.ui.charts import (allocation_plot, cluster_map, cluster_network, evidence_plot,
                                  gas_plot, merkle_path, sandbox_bar, sandbox_frontier,
                                  toy_figure)
from qf_hybrid.ui.formatting import safe_evidence_markdown
from qf_hybrid.ui.merkle_verify import verify_merkle_proof_with_trace
from qf_hybrid.ui.sandbox import FAMILIES, LABELS, cluster_snapshot, family_label, frozen_config, run_sandbox
from qf_hybrid.ui.whatif import (demo_bundle_from_allocation, run_custom_table,
                                 sample_donations, parse_donations)

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="QF · Chống thông đồng", page_icon="◈", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Crimson+Pro:wght@400;600&display=swap');
:root { color-scheme: light; }
.stApp { background: #F8FAFC; color: #172332; font-family: 'Atkinson Hyperlegible', Arial, sans-serif; }
.block-container { max-width: 1350px; padding-top: 1.1rem; }
h1,h2,h3 { font-family: 'Crimson Pro', Georgia, serif; color:#0F172A; }
h1 { letter-spacing: -.025em; margin-bottom:.15rem; }
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
.stDeployButton, a[data-testid="stHeaderActionElements"], [data-testid="stHeaderActionElements"] { display:none !important; }
header[data-testid="stHeader"] { display:none !important; }
[data-testid="stMetric"] { background: #FFFFFF; border:1px solid #DCE4EC; border-radius:12px; padding: .65rem .85rem; }
[data-testid="stMetricLabel"] { color:#334155; }
[data-testid="stTabs"] button { font-size: .94rem; font-weight:700; }
[data-testid="stTabs"] button[aria-selected="true"] { color:#0072B2; }
.qf-hero { border-left:5px solid #0072B2; padding:.55rem 1rem; background:#E8F2F8; border-radius:0 10px 10px 0; margin-bottom:.75rem; }
.qf-hero strong { display:block; color:#0F172A; font-family:'Crimson Pro',Georgia,serif; font-size:1.35rem; line-height:1.25; }
.qf-hero span { color:#334155; font-size:.91rem; }
.qf-steps { display:flex; gap:.45rem; flex-wrap:wrap; margin:.4rem 0 1rem; }
.qf-step { flex:1; min-width:180px; padding:.75rem; background:white; border:1px solid #DCE4EC; border-radius:10px; font-size:.86rem; }
.qf-step b { color:#0072B2; }
.qf-terms { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.6rem; margin:.7rem 0 .85rem; }
.qf-term { background:#FFFFFF; border:1px solid #DCE4EC; border-radius:10px; padding:.55rem .75rem; min-height:66px; }
.qf-term b { display:block; color:#0F172A; font-size:.92rem; }
.qf-term span { display:block; color:#475569; font-size:.79rem; line-height:1.3; }
@media (max-width:800px) { .qf-terms { grid-template-columns:repeat(2,minmax(0,1fr)); } }
.qf-note { background:#FFFFFF; border:1px solid #DCE4EC; border-left:4px solid #E69F00; padding:.8rem 1rem; border-radius:8px; margin:.6rem 0; }
.qf-success { border-left-color:#009E73; }
.qf-error { border-left-color:#D55E00; }
.qf-badge { display:inline-block; border:1px solid #7C97AB; background:#E8F2F8;
  border-radius:999px; padding:.24rem .7rem; color:#17364B; font-size:.78rem;
  font-weight:700; letter-spacing:.02em; margin:.25rem 0 .6rem; }
.qf-badge-locked { border-color:#7CA894; background:#E7F5EF; color:#17523E; }
.stButton button:focus-visible, .stSelectbox div:focus-visible { outline:3px solid #0072B2 !important; outline-offset:2px; }
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / path)


@st.cache_data(show_spinner=False)
def read_bundle(round_id: int) -> dict:
    return json.loads((ROOT / f"results/gas/demo_merkle_round_{round_id}.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def cached_sandbox(family: str, budget: int, m: int, seed: int, pool: int,
                   organic_wallets: int, custom_beta: dict,
                   custom_graph_key: tuple, custom_tau: int) -> dict:
    return run_sandbox(family, budget, m, seed, pool=pool,
                       organic_wallets=organic_wallets, custom_beta=custom_beta,
                       custom_graph_key=custom_graph_key, custom_tau=custom_tau)


@st.cache_resource(show_spinner=False)
def cached_clusters(with_attack: bool, overview: bool) -> dict:
    return cluster_snapshot(with_attack, overview)


def notice(message: str, kind: str = "note") -> None:
    message = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", message)
    st.markdown(f'<div class="qf-note qf-{kind}">{message}</div>', unsafe_allow_html=True)


def badge(label: str, locked: bool = False) -> None:
    suffix = " qf-badge-locked" if locked else ""
    st.markdown(f'<span class="qf-badge{suffix}">{label}</span>', unsafe_allow_html=True)


def custom_input_signature(frame: pd.DataFrame, assumptions: tuple) -> tuple:
    donations = parse_donations(frame)
    return assumptions, tuple((donor, project, str(amount))
                              for (donor, project), amount in sorted(donations.items()))


def discard_live_bundle(source: str) -> None:
    bundle = st.session_state.get("live_bundle")
    if bundle and str(bundle.get("demo_metadata", {}).get("source", "")).startswith(source):
        st.session_state.pop("live_bundle", None)
        st.session_state.merkle_source = "27"


SANDBOX_WIDGET_KEYS = ("whatif_pool", "whatif_organic", "whatif_beta0", "whatif_coh",
                       "whatif_conc", "whatif_shapley", "whatif_centrality", "whatif_k",
                       "whatif_resolution", "whatif_tau", "sandbox_mode", "form_family",
                       "form_budget", "form_m", "form_seed", "custom_payout_choice",
                       "redteam_payout_choice")


def restore_sandbox_widgets() -> None:
    for key, value in st.session_state.get("sandbox_widget_snapshot", {}).items():
        st.session_state.setdefault(key, value)


def save_sandbox_widgets() -> None:
    st.session_state.sandbox_widget_snapshot = {
        key: st.session_state[key] for key in SANDBOX_WIDGET_KEYS if key in st.session_state}


def plot(fig, key: str) -> None:
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False,
                    "toImageButtonOptions": {"format": "png", "filename": key}}, key=key)


def tamper_plus_one(amount_key: str, original_amount: str) -> None:
    try:
        st.session_state[amount_key] = str(int(st.session_state[amount_key]) + 1)
    except ValueError:
        st.session_state[amount_key] = str(int(original_amount) + 1)


def tamper_restore(amount_key: str, recipient_key: str, leaf: dict) -> None:
    st.session_state[amount_key] = leaf["amount"]
    st.session_state[recipient_key] = leaf["recipient"]


def tab_model() -> None:
    st.subheader("Từ một khoản tài trợ đến khoản chi trả có thể kiểm chứng")
    st.markdown("""<div class="qf-steps">
    <div class="qf-step"><b>01 · Dữ liệu</b><br>Ví → dự án → số tiền</div>
    <div class="qf-step"><b>02 · Đồ thị</b><br>Đồng đóng góp G1/G2 → Louvain</div>
    <div class="qf-step"><b>03 · Ngoài chuỗi</b><br>Chiết khấu mềm → phân bổ quỹ</div>
    <div class="qf-step"><b>04 · EVM cục bộ</b><br>Cam kết Merkle → proof → claim</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("#### Bóc tách một đòn chia ví")
    a, b, c = st.columns(3)
    with a:
        budget = st.slider("Ngân sách D (USD)", 50, 500, 100, key="toy_budget")
    with b:
        wallets = st.slider("Số ví m", 1, 50, 20, key="toy_wallets")
    with c:
        lam = st.slider("Hệ số nén λ", 0.0, 1.0, 0.80, step=.05, key="toy_lambda")
    left, right = st.columns([1.45, 1], gap="large")
    fig, values = toy_figure(budget, wallets, lam)
    with left:
        plot(fig, "minh_hoa_chia_vi")
    with right:
        st.metric("Matching thô khi chia ví", f"{values['raw']:,.1f} USD")
        st.metric("Sau nén mềm", f"{values['soft']:,.1f} USD")
        st.markdown(f"""√D = **{values['one_root']:.3f}** · √(Dm) = **{values['split_root']:.3f}**  
        a hiệu dụng = (1 − {lam:.2f}) × √(Dm) + {lam:.2f} × √D = **{values['effective_root']:.3f}**  
        Matching thô = max(0, a² − D).""")
    if wallets == 1:
        notice("Một ví đóng góp một dự án tạo matching thô bằng 0 trong ví dụ tách biệt này.")
    elif lam < 1:
        notice("λ &lt; 1 vẫn để lại lợi ích chia ví. Mô hình này chỉ triệt tiêu đúng tại λ = 1 nếu toàn bộ ví giả được giữ trong cùng một cụm.")
    else:
        notice("λ = 1 triệt tiêu lợi ích chia ví trong ví dụ cụm cố định; Louvain thực tế có thể tách cụm.", "success")
    st.markdown("#### Phản ví dụ nhận dạng")
    x, y = st.columns(2)
    x.info("**50 người thật** cùng đóng góp vào một dự án có thể tạo 50 dòng đóng góp tương tự nhau.")
    y.warning("**Một người dùng 50 ví** cũng có thể tạo đúng ma trận đóng góp đó. Chỉ nhìn bảng giao dịch không thể phân biệt chắc chắn.")


def tab_clusters() -> None:
    st.subheader("Cụm Louvain là giả thuyết cấu trúc, không phải nhãn Sybil")
    world = st.radio("Thế giới mẫu", ["Cộng đồng hợp lệ tập trung", "Sybil ngụy trang với decoy"],
                     horizontal=True, key="cluster_world")
    view = st.radio("Độ chi tiết đồ thị", ["Soi nhiều cụm (G2 · k=10 · γ=1,5)",
                                            "Tổng quan cụm lớn (G2 · k=40 · γ=0,5)"],
                    horizontal=True, key="cluster_view")
    overview = view.startswith("Tổng quan")
    with_attack = world.startswith("Sybil")
    snapshot = cached_clusters(with_attack, overview)
    rows = snapshot["rows"]
    honest = [r for r in rows if r["attackers"] == 0 and r["size"] > 1]
    attack = [r for r in rows if r["attackers"] > 0]
    pick_honest = max(honest, key=lambda r: (r["shapley"], r["lambda_full"]-r["lambda_base"])) if honest else rows[0]
    pick_attack = max(attack, key=lambda r: (r["attackers"], r["size"])) if attack else rows[0]
    if "selected_cluster" not in st.session_state or st.session_state.get("selected_cluster_world") != (world, view):
        st.session_state.selected_cluster = pick_honest["id"]
        st.session_state.selected_cluster_world = (world, view)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### Bản đồ cụm")
        plot(cluster_map(rows, st.session_state.selected_cluster), "ban_do_cum")
        st.caption("Mỗi vòng tròn là một cụm. Màu phản ánh nhãn tiêm có kiểm soát trong dữ liệu synthetic.")
    with right:
        st.markdown("##### Soi một cụm")
        p, q = st.columns(2)
        if p.button("Cụm hợp lệ có Sₖ cao", width="stretch"):
            st.session_state.selected_cluster = pick_honest["id"]
        if q.button("Cụm chứa ví tấn công", width="stretch", disabled=not attack):
            st.session_state.selected_cluster = pick_attack["id"]
        selected = st.selectbox("Chọn mã cụm", [r["id"] for r in rows],
                                format_func=lambda i: f"Cụm {i} · {rows[i-1]['size']} ví",
                                key="selected_cluster")
        row = rows[selected-1]
        metrics = st.columns(4)
        metrics[0].metric("Gắn kết", f"{row['cohesion']:.2f}")
        metrics[1].metric("Sₖ", f"{row['shapley']:.2f}")
        metrics[2].metric("λ Base", f"{row['lambda_base']:.2f}")
        metrics[3].metric("λ Full", f"{row['lambda_full']:.2f}")
        shown_members = row["members"][:50]
        plot(cluster_network(snapshot["graph"], shown_members, snapshot["events"]), "mang_noi_cum")
        if len(row["members"]) > len(shown_members):
            st.caption(f"Hiển thị 50/{len(row['members'])} ví đầu theo mã để đồ thị dễ đọc; chỉ số bên dưới vẫn tính trên toàn cụm.")
    frame = pd.DataFrame([{"Chỉ số": "Số ví", "Giá trị": str(row["size"])},
                          {"Chỉ số": "Ví tấn công được tiêm", "Giá trị": str(row["attackers"])},
                          {"Chỉ số": "Độ gắn kết", "Giá trị": f"{row['cohesion']:.3f}"},
                          {"Chỉ số": "Tỷ trọng nội cụm Sₖ", "Giá trị": f"{row['shapley']:.3f}"},
                          {"Chỉ số": "λ · Soft Base", "Giá trị": f"{row['lambda_base']:.3f}"},
                          {"Chỉ số": "λ · Soft Full", "Giá trị": f"{row['lambda_full']:.3f}"}])
    st.dataframe(frame, hide_index=True, width="stretch")
    st.caption("Hai hệ số λ ở đây được tính trên cùng phân hoạch đang xem để so sánh đặc trưng. Kết quả phân bổ Phase 2 dùng khóa đồ thị riêng cho từng cơ chế theo cấu hình đã khóa.")
    if row["attackers"] == 0:
        notice("Cụm này không chứa ví tấn công trong dữ liệu synthetic. Sₖ cao vẫn có thể là hành vi cộng đồng thật; λ chỉ là hệ số của cơ chế, không phải xác suất Sybil.")
    else:
        notice("Cụm này chứa ví tấn công đã tiêm. Màu sắc và nhãn này chỉ có vì thí nghiệm kiểm soát; dữ liệu Gitcoin thật không có ground truth tương đương.")


def tab_sandbox() -> None:
    st.subheader("Phòng thí nghiệm Red Team trực tiếp")
    restore_sandbox_widgets()
    selected = frozen_config()
    base = selected["soft_base"]
    with st.expander("Tùy chỉnh giả định mô hình & phòng thủ (What-If)", expanded=False):
        st.caption("Mặc định trùng cấu hình Soft Base Phase 2 tại ngưỡng 5%. Mọi thay đổi chỉ dùng cho demo phiên này; bảng và báo cáo đã khóa không bị ghi đè.")
        market = st.columns(2)
        pool = market[0].number_input("Quỹ đối ứng B (USD)", min_value=1000,
                                      max_value=1_000_000, value=10_000, step=1000,
                                      key="whatif_pool")
        organic_wallets = market[1].slider("Số ví hợp lệ tập trung", 0, 100, 50,
                                            key="whatif_organic")
        weight_cols = st.columns(5)
        beta0 = weight_cols[0].slider("β₀", -1.0, 1.0, float(base["beta"]["beta0"]), .05, key="whatif_beta0")
        beta_coh = weight_cols[1].slider("β gắn kết", -1.0, 1.5, float(base["beta"]["coh"]), .05, key="whatif_coh")
        beta_conc = weight_cols[2].slider("β tập trung", -1.0, 1.5, float(base["beta"]["conc"]), .05, key="whatif_conc")
        beta_s = weight_cols[3].slider("β Shapley", -1.0, 1.5, 0.0, .05, key="whatif_shapley")
        beta_c = weight_cols[4].slider("β trung tâm", -1.0, 1.5, 0.0, .05, key="whatif_centrality")
        graph_cols = st.columns(3)
        k = graph_cols[0].selectbox("Số láng giềng k", [10, 20, 40], index=2, key="whatif_k")
        resolution = graph_cols[1].select_slider("Độ phân giải Louvain γ",
                                                  options=[0.5, 1.0, 1.5], value=0.5,
                                                  key="whatif_resolution")
        tau = graph_cols[2].slider("Ngưỡng Pairwise τ", 1, 2000, 500,
                                    key="whatif_tau")
        st.caption("B thay đổi số USD phân bổ, còn tỷ lệ % B thường không đổi khi chỉ nhân cùng một quỹ. τ tùy chỉnh xuất hiện thành một dòng Pairwise riêng; dòng Pairwise gốc vẫn dùng τ=500.")
    beta = {"beta0": beta0, "coh": beta_coh, "conc": beta_conc,
            "shapley": beta_s, "centrality": beta_c, "size": 0.0}
    graph_key = ("G2", k, resolution)
    assumptions = (int(pool), tuple(sorted(beta.items())), graph_key, int(tau))
    mode = st.radio("Nguồn đóng góp", ["Kịch bản Red Team", "Bảng đóng góp của tôi"],
                    horizontal=True, key="sandbox_mode")
    if mode == "Bảng đóng góp của tôi":
        badge("CHẠY DEMO CỤC BỘ · PHẢN THỰC TRONG PHIÊN")
        if "custom_table_sample" not in st.session_state:
            st.session_state.custom_table_sample = sample_donations()
        st.caption("Các dòng trùng (Ví, Dự án) được cộng gộp theo MATH_SPEC trước khi tính. Chỉnh bảng không tự chạy lại mô phỏng.")
        if st.button("Nạp lại kịch bản mẫu (10 dòng)", key="custom_reset"):
            st.session_state.custom_table_sample = sample_donations()
            st.session_state.pop("custom_table_draft", None)
            st.session_state.custom_editor_version = st.session_state.get("custom_editor_version", 0) + 1
            st.session_state.pop("custom_table_result", None)
            st.session_state.pop("custom_table_signature", None)
            discard_live_bundle("Bảng đóng góp tự nhập")
            st.rerun()
        editor_key = f"custom_editor_{st.session_state.get('custom_editor_version', 0)}"
        if editor_key not in st.session_state and "custom_table_draft" in st.session_state:
            st.session_state.custom_table_sample = st.session_state.custom_table_draft.copy(deep=True)
        edited = st.data_editor(st.session_state.custom_table_sample,
                                num_rows="dynamic", hide_index=True, width="stretch",
                                key=editor_key)
        st.session_state.custom_table_draft = edited.copy(deep=True)
        calculate = st.button("Tính phân bổ trực tiếp", type="primary",
                              key="custom_calculate")
        input_error = None
        try:
            signature = custom_input_signature(edited, assumptions)
        except ValueError as error:
            signature = None
            input_error = str(error)
        stale = signature is None or st.session_state.get("custom_table_signature") != signature
        if stale:
            discard_live_bundle("Bảng đóng góp tự nhập")
        if calculate or "custom_table_result" not in st.session_state:
            if input_error:
                st.error(input_error)
            else:
                try:
                    with st.spinner("Đang tính phân bổ từ bảng đã chốt..."):
                        st.session_state.custom_table_result = run_custom_table(
                            edited, pool=int(pool), beta=beta, graph_key=graph_key, tau=int(tau))
                    st.session_state.custom_table_signature = signature
                    stale = False
                    discard_live_bundle("Bảng đóng góp tự nhập")
                except ValueError as error:
                    st.error(str(error))
        if "custom_table_result" not in st.session_state:
            save_sandbox_widgets()
            return
        if stale:
            st.warning("Tham số hoặc bảng đóng góp vừa thay đổi — kết quả bên dưới thuộc lần tính trước. Hãy bấm Tính phân bổ trực tiếp để cập nhật.")
            if input_error and not calculate:
                st.error(input_error)
        result = st.session_state.custom_table_result
        st.caption(f"Kết quả lần tính cuối: B={result['pool']:,.0f} USD, hoàn thành trong {result['seconds']:.3f} giây. Dữ liệu gõ tay chỉ tồn tại trong phiên demo; không có nhãn Sybil hoặc cặp thế giới đối chứng.")
        allocs = result["allocations"]
        columns = {key: "Tùy chỉnh của tôi" if key == "custom_soft" else LABELS[key]
                   for key in allocs}
        table = pd.DataFrame({"Dự án": result["projects"],
                              **{label: [f"{values[p]:,.2f}" for p in result["projects"]]
                                 for key, values in allocs.items()
                                 for label in [columns[key]]}})
        st.dataframe(table, hide_index=True, width="stretch")
        plot(allocation_plot(allocs), "phan_bo_bang_tu_nhap")
        payout_options = list(allocs)
        payout_choice = st.selectbox("Cơ chế dùng để sinh payout demo", payout_options,
                                     format_func=lambda key: columns[key], key="custom_payout_choice")
        if result["unallocated"][payout_choice] >= result["pool"]:
            st.info("Matching bằng 0; toàn bộ B chưa phân bổ. Không có khoản chi dương để tạo Merkle root.")
        if st.button("Sinh cây Merkle trực tiếp từ kết quả này", key="build_custom_merkle",
                     disabled=stale or result["unallocated"][payout_choice] >= result["pool"]):
            try:
                st.session_state.live_bundle = demo_bundle_from_allocation(
                    allocs[payout_choice], pool_usd=result["pool"],
                    source_label="Bảng đóng góp tự nhập", mechanism_label=columns[payout_choice])
                st.session_state.merkle_source = "live"
                st.success("Đã sinh proof trong bộ nhớ. Mở Tab 04 để thử xác thực và sửa giả mạo.")
            except ValueError as error:
                st.error(str(error))
        save_sandbox_widgets()
        return
    badge("CHẠY DEMO CỤC BỘ · PHẢN THỰC TRONG PHIÊN")
    defaults = {"family": "decoy_camouflage", "budget": 500, "m": 40, "seed": 100}
    if "sandbox_params" not in st.session_state:
        st.session_state.sandbox_params = defaults.copy()
    preset_cols = st.columns(3)
    presets = [("Chia ví thuần", {"family": "pure_split", "budget": 500, "m": 40, "seed": 100}),
               ("Ngụy trang decoy", defaults),
               ("Tách cụm", {"family": "cross_cluster_split", "budget": 500, "m": 40, "seed": 100})]
    for col, (label, params) in zip(preset_cols, presets):
        active = st.session_state.get("form_family", st.session_state.sandbox_params["family"]) == params["family"]
        if col.button(label, key=f"preset_{params['family']}", width="stretch",
                      type="primary" if active else "secondary"):
            for field, value in params.items():
                st.session_state[f"form_{field}"] = value
            st.rerun()
    current = st.session_state.sandbox_params
    for field, value in current.items():
        st.session_state.setdefault(f"form_{field}", value)
    cols = st.columns(4)
    family = cols[0].selectbox("Họ tấn công", list(FAMILIES),
                               format_func=lambda key: FAMILIES[key], key="form_family")
    budget = cols[1].number_input("Ngân sách D (USD)", 50, 2000, step=50, key="form_budget")
    m = cols[2].number_input("Số ví m", 1, 100, key="form_m")
    seed = cols[3].number_input("Seed", 1, 100000, key="form_seed")
    candidate = {"family": family, "budget": int(budget), "m": int(m), "seed": int(seed)}
    signature = (assumptions, int(organic_wallets), *candidate.values())
    submitted = st.button("Chạy so sánh trực tiếp", type="primary", key="sandbox_calculate")
    stale = st.session_state.get("sandbox_signature") != signature
    if stale:
        discard_live_bundle("Red Team synthetic")
    if submitted or "sandbox_result" not in st.session_state:
        with st.spinner("Đang xây dựng hai thế giới đối chứng và tính phân bổ..."):
            st.session_state.sandbox_result = cached_sandbox(
                **candidate, pool=int(pool), organic_wallets=int(organic_wallets),
                custom_beta=beta, custom_graph_key=graph_key, custom_tau=int(tau))
        st.session_state.sandbox_params = candidate
        st.session_state.sandbox_signature = signature
        stale = False
        discard_live_bundle("Red Team synthetic")
    result = st.session_state.sandbox_result
    current = st.session_state.sandbox_params
    if stale:
        st.warning("Tham số kịch bản hoặc What-If vừa thay đổi — kết quả bên dưới thuộc lần tính trước. Hãy bấm Chạy so sánh trực tiếp để cập nhật.")
    rows = result["rows"]
    st.caption(f"Kết quả lần tính cuối: synthetic seed #{current['seed']}, B={result['pool']:,.0f} USD, hoàn thành trong {result['seconds']:.2f} giây. Các dòng gốc dùng cấu hình Phase 2 đã khóa; dòng tùy chỉnh dùng giả định của lần tính này và không ghi đè thí nghiệm Phase 2.")
    eligible = [r for r in rows if r["policy_ok"]]
    winner = min(eligible, key=lambda r: r["gain_pct"]) if eligible else None
    if winner:
        notice(f"Trong thế giới thử này, **{winner['label']}** có lợi ích tấn công thấp nhất trong các cơ chế giữ tổn hại cộng đồng ≤ 5% B. Kết luận chỉ áp dụng cho tham số đang hiển thị.", "success")
    else:
        notice("Không cơ chế nào trong bảng đạt ngưỡng tổn hại cộng đồng 5% B ở tham số đang chọn.", "error")
    table = pd.DataFrame([{"Cơ chế": r["label"], "Lợi ích tấn công (% B)": f"{r['gain_pct']:.3f}",
                           "Tổn hại cộng đồng (% B)": f"{r['damage_pct']:.3f}",
                           "Ngưỡng 5%": "Đạt" if r["policy_ok"] else "Vượt"} for r in rows])
    st.dataframe(table.style.map(lambda value: "color:#D55E00;font-weight:700" if value == "Vượt" else "color:#007B5E", subset=["Ngưỡng 5%"]),
                 hide_index=True, width="stretch")
    a, b = st.columns(2, gap="large")
    with a:
        plot(sandbox_bar(rows), "loi_ich_va_ton_hai")
    with b:
        plot(sandbox_frontier(rows), "mat_tran_danh_doi")
    st.caption(f"Lợi ích tấn công = phần tăng phân bổ cho dự án mục tiêu giữa hai thế giới ghép cặp, chia cho B={result['pool']:,.0f} USD của lần tính cuối. Đây không phải lợi nhuận ròng.")
    labels = {row["mechanism"]: row["label"] for row in rows}
    payout_choice = st.selectbox("Cơ chế dùng để sinh payout demo", list(result["allocations"]),
                                 format_func=lambda key: labels[key], key="redteam_payout_choice")
    if st.button("Sinh cây Merkle trực tiếp từ kết quả này", key="build_redteam_merkle", disabled=stale):
        try:
            st.session_state.live_bundle = demo_bundle_from_allocation(
                result["allocations"][payout_choice], pool_usd=result["pool"],
                source_label=f"Red Team synthetic · seed {current['seed']}",
                mechanism_label=labels[payout_choice])
            st.session_state.merkle_source = "live"
            st.success("Đã sinh proof trong bộ nhớ. Mở Tab 04 để thử xác thực và sửa giả mạo.")
        except ValueError as error:
            st.error(str(error))
    save_sandbox_widgets()


def tab_merkle() -> None:
    st.subheader("Proof Merkle và chi phí Gas EVM cục bộ")
    sources = ["27", "867"]
    if "live_bundle" in st.session_state:
        sources.append("live")
    source = st.selectbox("Nguồn bảng chi trả", sources,
                          format_func=lambda value: "Kết quả vừa chạy ở Tab 03 · demo cục bộ" if value == "live"
                          else f"Gitcoin 42161:{value} · {46 if value == '27' else 142} dự án",
                          key="merkle_source")
    bundle = st.session_state.live_bundle if source == "live" else read_bundle(int(source))
    badge("ROOT DEMO CỤC BỘ · CHƯA TRIỂN KHAI LÊN CHAIN")
    if source == "live":
        meta = bundle["demo_metadata"]
        st.caption(f"Bản demo từ {meta['source']} · {meta['mechanism']}. Root sinh trong bộ nhớ, chưa xuất bản lên chain; pool EVM thử nghiệm 1 ETH chỉ tỷ lệ với phân bổ USD, không phải quy đổi tiền tệ.")
    grants = [str(row["grant_id"]) for row in bundle["leaves"]]
    grant = st.selectbox("Mã dự án", grants,
                         format_func=lambda value: f"{value} · {bundle['demo_metadata']['project_map'][value]}"
                         if source == "live" else value, key="merkle_grant")
    leaf = next(row for row in bundle["leaves"] if str(row["grant_id"]) == grant)
    amount_key = f"tamper_amount_{source}_{bundle['root']}_{grant}"
    recipient_key = f"tamper_recipient_{source}_{bundle['root']}_{grant}"
    if amount_key not in st.session_state:
        st.session_state[amount_key] = leaf["amount"]
    if recipient_key not in st.session_state:
        st.session_state[recipient_key] = leaf["recipient"]
    a, b, c = st.columns([1.5, 1.5, 1])
    with a:
        st.text_input("Số tiền claim (wei)", key=amount_key)
    with b:
        st.text_input("Địa chỉ nhận", key=recipient_key)
    with c:
        st.write("")
        st.button("Sửa +1 wei", width="stretch", key="tamper_plus_one",
                  on_click=tamper_plus_one, args=(amount_key, leaf["amount"]))
        st.button("Khôi phục", width="stretch", key="tamper_restore",
                  on_click=tamper_restore, args=(amount_key, recipient_key, leaf))
    try:
        result = verify_merkle_proof_with_trace(bundle, grant,
                    amount_override=st.session_state[amount_key],
                    recipient_override=st.session_state[recipient_key])
    except (ValueError, OverflowError) as error:
        st.error(f"Dữ liệu nhập không hợp lệ: {error}")
        return
    if result["valid"]:
        notice("**XÁC THỰC HỢP LỆ** · Root tính từ proof khớp từng byte với root tham chiếu trong bundle.", "success")
    else:
        notice(f"**BỊ TỪ CHỐI** · Sai khác bắt đầu từ tầng {result['first_divergence_level']}; nhánh tính lại không khớp root tham chiếu.", "error")
    plot(merkle_path(result["trace"], result["valid"]), "duong_di_merkle")
    st.code(f"Root tính lại: {result['computed_root']}\nRoot tham chiếu: {result['expected_root']}", language="text")
    labels = {"schema_version": "Phiên bản leaf", "chain_id": "Chain ID", "vault_address": "Địa chỉ vault demo",
              "asset_address": "Địa chỉ tài sản", "round_id": "Mã vòng", "grant_id": "Mã dự án",
              "recipient": "Địa chỉ nhận", "amount": "Số tiền (wei)"}
    st.dataframe(pd.DataFrame([{"Trường ABI": labels[key], "Giá trị đang thử": value} for key, value in result["fields"].items()]),
                 hide_index=True, width="stretch")
    notice("**Mô hình tin cậy:** proof chỉ chứng minh khoản chi thuộc bảng payout mà owner đã cam kết. Nó không kiểm chứng dữ liệu đầu vào, kết quả Louvain hay tính đúng đắn của phép tính ngoài chuỗi. Root này là **cam kết demo cục bộ, chưa xuất bản lên chain**; địa chỉ vault demo chưa được triển khai.")
    st.markdown("#### Gas đã đo bằng receipt EVM")
    gas = read_csv("results/gas/phase3_gas_benchmark.csv")
    row = gas.loc[gas["n"] == 1000].iloc[0]
    cols = st.columns(4)
    cols[0].metric("Tiết kiệm publish", f"{row['publish_saving_pct']:.1f}%")
    cols[1].metric("Lifecycle · claim 100%", f"{row['lifecycle_saving_100pct']:.1f}%")
    cols[2].metric("Lifecycle · claim 25%", f"{row['lifecycle_saving_25pct']:.1f}%")
    cols[3].metric("Chênh lệch mỗi claim", f"+{row['merkle_claim_mean']-row['naive_claim_mean']:,.0f} gas")
    claim = st.radio("Tỷ lệ thực hiện claim", [25, 50, 100], index=2,
                     format_func=lambda value: f"{value}%", horizontal=True, key="gas_claim")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### A · Chi phí Publish của Admin")
        plot(gas_plot(gas), "gas_publish")
    with right:
        st.markdown("##### B · Tổng chi phí vòng đời (Publish + Claim)")
        plot(gas_plot(gas, claim), "gas_lifecycle")
    st.caption("Publish do admin trả; claim do người gọi claim trả. Lifecycle cộng cả hai phía. Break-even = 0 trong khoảng benchmark đã đo nghĩa là Merkle tiết kiệm tổng gas ngay cả khi toàn bộ khoản chi được claim; không phải kết quả cho mọi N hay phí USD mainnet.")


def tab_evidence() -> None:
    st.subheader("Bằng chứng đã khóa và giới hạn suy luận")
    badge("BẰNG CHỨNG NGHIÊN CỨU ĐÃ KHÓA · PHASE 2–3", locked=True)
    synthetic = read_csv("results/tables/phase2_heldout_synthetic.csv")
    empirical = read_csv("results/tables/phase2_heldout_empirical.csv")
    options = [value for value in synthetic["family"].unique() if "organic" not in value]
    families = st.multiselect("Họ tấn công synthetic", options, default=options[:3],
                              format_func=family_label,
                              key="evidence_families")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("##### Synthetic held-out")
        plot(evidence_plot(synthetic[synthetic["family"].isin(families)], empirical=False), "bang_chung_synthetic")
    with b:
        st.markdown("##### Gitcoin thật · vòng 865, 867, 29")
        unique = empirical.drop_duplicates(subset=["round_id", "family", "mechanism", "design_seed"])
        plot(evidence_plot(unique, empirical=True), "bang_chung_gitcoin")
    st.caption("Dữ liệu Gitcoin không có nhãn Sybil chuẩn. Các lần seed trùng thiết kế đã được loại khi hiển thị để tránh đếm lặp; DiffVsStandard đo độ lệch phân bổ, không phải phạt oan.")
    st.markdown("#### Kiểm định ghép cặp")
    stats = read_csv("results/tables/phase2_paired_ablation_stats.csv")
    shown = stats[["comparison_family", "first", "second", "metric", "n_trial_pairs",
                   "n_seed_blocks", "mean_diff", "p_holm"]].copy()
    shown.columns = ["Nhóm", "Cơ chế 1", "Cơ chế 2", "Chỉ số", "Số cặp (khối seed)",
                     "Khối seed", "Chênh lệch (% B)", "p Holm"]
    shown["Số cặp (khối seed)"] = (shown["Số cặp (khối seed)"].astype(str) + " (" +
                                    shown["Khối seed"].astype(str) + ")")
    shown = shown.drop(columns="Khối seed")
    shown["Nhóm"] = shown["Nhóm"].map({"ablation": "Loại bỏ thành phần", "baseline": "So với đối chứng"}).fillna(shown["Nhóm"])
    shown["Cơ chế 1"] = shown["Cơ chế 1"].map(LABELS).fillna(shown["Cơ chế 1"])
    shown["Cơ chế 2"] = shown["Cơ chế 2"].map(LABELS).fillna(shown["Cơ chế 2"])
    shown["Chỉ số"] = shown["Chỉ số"].map({"delta_A_pos_pct": "Lợi ích tấn công (% B)",
                                               "mech_damage_H": "Tổn hại cộng đồng"}).fillna(shown["Chỉ số"])
    shown["Chênh lệch (% B)"] = (shown["Chênh lệch (% B)"]*100).map(lambda value: f"{value:.4f}")
    shown["p Holm"] = shown["p Holm"].map(lambda value: f"{value:.4f}")
    st.dataframe(shown.style.map(lambda value: "background-color:#DDF4EB" if float(value) < .05 else "", subset=["p Holm"]),
                 hide_index=True, width="stretch")
    notice("Trên synthetic held-out, thêm Shapley và centrality không cải thiện lựa chọn cân bằng Soft Base theo giao thức đã khóa. Các chênh lệch rất nhỏ cỡ 10⁻¹⁹ chịu ảnh hưởng quy tắc phá hòa; không diễn giải thành phát hiện thực địa.")
    with st.expander("Ma trận nhận định · bằng chứng · giới hạn", expanded=False):
        st.markdown(safe_evidence_markdown((ROOT / "docs/CLAIMS_EVIDENCE_LIMITS.md").read_text(encoding="utf-8")))
        st.caption("Tên tệp nội bộ được hiển thị dạng chữ; tải tài liệu và dữ liệu từ các nút bên dưới.")
    st.markdown("#### Bốn hình nghiên cứu · 300 DPI")
    figures = [("Biên đánh đổi tại Dev", "fig01_tradeoff_frontier_dev.png"),
               ("Synthetic held-out", "fig02_heldout_synthetic_ablation.png"),
               ("Gitcoin held-out", "fig03_heldout_empirical_gitcoin.png"),
               ("Benchmark gas", "fig04_gas_benchmark.png")]
    name = st.selectbox("Chọn hình", [title for title, _ in figures], key="figure_select")
    filename = dict(figures)[name]
    path = ROOT / "results/figures" / filename
    st.image(str(path), caption=name, width=760)
    st.download_button("Tải hình PNG", data=path.read_bytes(), file_name=filename, mime="image/png")
    cols = st.columns(3)
    files = [("Báo cáo học thuật", "REPORT.md", "text/markdown"),
             ("CSV synthetic", "results/tables/phase2_heldout_synthetic.csv", "text/csv"),
             ("CSV Gitcoin", "results/tables/phase2_heldout_empirical.csv", "text/csv")]
    for col, (label, file, mime) in zip(cols, files):
        col.download_button(f"Tải {label}", data=(ROOT/file).read_bytes(),
                            file_name=Path(file).name, mime=mime, width="stretch")


st.markdown('<div class="qf-hero"><strong>QF · Chống thông đồng</strong><span>Từ trực giác toán học đến đối chứng Red Team, proof Merkle và giới hạn của bằng chứng.</span></div>', unsafe_allow_html=True)
st.markdown('''<div class="qf-terms">
<div class="qf-term"><b>QF</b><span>Matching tăng khi nhiều người ủng hộ.</span></div>
<div class="qf-term"><b>Chia ví Sybil</b><span>Một người chia tiền qua nhiều ví.</span></div>
<div class="qf-term"><b>Tổn hại cộng đồng</b><span>Phần phân bổ mất đi của dự án hợp lệ.</span></div>
<div class="qf-term"><b>Merkle Proof</b><span>Chứng minh khoản chi thuộc bảng đã cam kết.</span></div>
</div>''', unsafe_allow_html=True)

tabs = st.tabs(["01 · Hiểu mô hình", "02 · Soi cụm", "03 · Red Team",
                "04 · Merkle & Gas", "05 · Bằng chứng"], on_change="rerun", key="active_tab")
renderers = (tab_model, tab_clusters, tab_sandbox, tab_merkle, tab_evidence)
for tab, render in zip(tabs, renderers):
    with tab:
        if tab.open:
            render()

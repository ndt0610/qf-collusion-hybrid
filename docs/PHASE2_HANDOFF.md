# Bàn giao Giai đoạn 2 — Red Team, ablation và held-out

**Trạng thái:** Đã chạy xong giao thức Phase 2; chưa triển khai EVM/Merkle/Gas. Hai tệp brief chủ dự án gửi có nội dung trùng nhau. Cấu hình được chọn trên dev và lưu vào `configs/heldout/frozen_mechanisms.json` **trước** lượt chạy held-out. Lượt held-out chỉ đọc cấu hình đã khóa ở ngưỡng chính 5%.

Các điểm 2% và 10% đã được khóa trên dev để xem đường đánh đổi, nhưng không chạy thêm trên held-out; phần đánh giá held-out gồm đúng 9 cơ chế tại ngưỡng chính 5%.

## Tái lập và log

| Lệnh | Kết quả |
|---|---:|
| `.venv\Scripts\python.exe scripts\run_phase2_dev.py` | 139.0 giây wall-clock; 18 cấu hình được chọn cho 6 cơ chế × 3 ngưỡng |
| `.venv\Scripts\python.exe scripts\run_phase2_heldout.py` | 213.9 giây wall-clock; 360 dòng synthetic, 405 dòng empirical |
| `.venv\Scripts\python.exe -m pytest -q` | 32 passed |
| `.venv\Scripts\python.exe -m pip check` | No broken requirements found |

Hai lượt chạy riêng biệt; số giây bên trên không bao gồm tải/kiểm toán dữ liệu Phase 1 và bước tạo biểu đồ. Bảng runtime chi tiết: `results/tables/phase2_dev_runtime.json`, `phase2_heldout_runtime.json`. Script `bench_pairwise.py` đo riêng đường tính thưa trên các vòng `27`, `865`, `867`: **0.93, 2.19, 0.51 giây** tương ứng cho dựng Gram thưa và quét năm τ; không gồm đọc Parquet. [Bảng benchmark](../results/tables/phase2_pairwise_sparse_benchmark.md).

## Cấu hình Dev đã khóa ở ngưỡng 5%

| Cơ chế | Đồ thị (k, resolution) | Hệ số được chọn | Damage dev | Attack gain dev |
|---|---|---|---:|---:|
| `pairwise_qf` | không dùng | τ=500 | 1.205% B | 1.078% B |
| `size_only` | G2 (10, 1.5) | β₀=0, βsize=0.8 | 3.093% B | 0.919% B |
| `soft_base` | G2 (40, 0.5) | β₀=−0.5, βcoh=0.8, βconc=0.8 | 4.267% B | 0.0616% B |
| `soft_shapley` | G2 (10, 0.5) | β₀=−0.25, βconc=0.8, **βS=0.8** | 4.926% B | ~0% B |
| `soft_centrality` | G2 (40, 0.5) | β₀=−0.5, βcoh=0.8, βconc=0.8, **βC=−0.6** | 4.220% B | 0.0614% B |
| `soft_full` | G2 (10, 0.5) | β₀=−0.25, βconc=0.8, **βS=0.8, βC=−0.6** | 4.993% B | ~0% B |

Giá trị gần 0 ở dev là kết quả trong các họ tấn công dev đã định, không chứng minh bất biến với tấn công thích nghi. Cả 2% và 10% cũng đã được chọn và lưu; [bảng đầy đủ](../results/tables/phase2_dev_selection.md), [38 điểm Pareto không bị trội](../results/tables/phase2_dev_pareto.md), [toàn bộ lưới 14.821 cấu hình](../results/tables/phase2_dev_frontier.csv), [cấu hình khóa](../configs/heldout/frozen_mechanisms.json).

**Kiểm toán số học sau khi đã xem held-out:** Quy tắc Dev đã so sánh trực tiếp các số float rất nhỏ. Có 8 ứng viên `soft_shapley` và 40 ứng viên `soft_full` trong ngưỡng damage 5% với gain `<10⁻¹² B`; chênh lệch gain của chúng chỉ cỡ `10⁻¹⁹ B`. Nếu quy ước các giá trị này bằng 0 trước tie-break, ứng viên có damage dev thấp nhất sẽ là 3.859% (`soft_shapley`) và 3.830% (`soft_full`), thay vì 4.926% và 4.993% đã khóa. Đây là **độ nhạy của việc chọn cấu hình**, không phải kết quả held-out của các ứng viên thay thế. Vì phát hiện sau khi mở held-out, chúng tôi không đổi cấu hình, không chạy ứng viên thay thế trên held-out và không trình bày nghiên cứu này như một xác nhận chắc chắn cho cấu hình tối ưu. [Bảng kiểm toán](../results/tables/phase2_numerical_selection_audit.md).

## Synthetic held-out: kiểm định các giả thuyết

Đơn vị là % quỹ B=USD 10.000. Attack gain là trung bình dương trên ba họ `decoy_camouflage`, `cross_cluster_split`, `ring_4proj` (10 seed/họ). Damage đo trên 10 vòng nền `strongly_concentrated_organic` không có attack, gồm 40 ví chỉ đóng một dự án. Đây là nhóm hợp lệ *theo thiết kế synthetic*, không phải nhãn của Gitcoin.

| Cơ chế | Attack gain (% B) ↓ | Damage organic (% B) ↓ |
|---|---:|---:|
| Standard QF | 1.470 | 0.000 |
| Pairwise QF | 1.552 | 0.446 |
| CO-QF paper 2025 Alg. 2 | **0.133** | 24.928 |
| HardCluster | 3.079 | 25.265 |
| size_only | 1.121 | 4.799 |
| soft_base | **1.101** | **2.995** |
| soft_shapley | 2.352 | 3.961 |
| soft_centrality | 1.104 | 2.993 |
| soft_full | 2.387 | 3.942 |

**Phản biện kết quả:** βS=0.8 đã được chọn trên dev, nhưng Shapley branch và full branch **kém hơn** `soft_base` trên held-out, cả ở gain lẫn damage organic. βC=−0.6 chỉ làm thay đổi rất nhỏ và không tạo lợi ích chặn attack: `soft_centrality` có gain cao hơn `soft_base` khoảng **0.0025 điểm phần trăm quỹ**, dù damage organic thấp hơn khoảng 0.002 điểm. Không có bằng chứng để tuyên bố Shapley hoặc Centrality mang giá trị bổ sung vững trên tập held-out này. `soft_base` còn tốt hơn `size_only` về cả hai chỉ số trung bình này. Pairwise τ=500 gần Standard và không cải thiện gain tổng hợp synthetic. CO-QF chặn gain tốt nhưng tổn hại organic vượt ngưỡng chính 5% khoảng năm lần; không thể chọn chỉ bằng một trục an toàn. HardCluster vừa gây damage lớn vừa thất bại ở tấn công tách cụm.

Kiểm định ghép cặp trên **10 khối seed** (mỗi seed dùng chung nền cho 3 họ, tổng 30 cặp trial), 10.000 bootstrap, sign-flip hai phía và Holm trong từng gia đình so sánh: `soft_full − soft_base` về gain dương = **+1.286 điểm phần trăm B**, CI 95% **[+1.160, +1.389]**, `p_holm=0.0078`; `soft_shapley − soft_base` = **+1.251 điểm**, `p_holm=0.0078`. `soft_centrality − soft_base` = **+0.0025 điểm**, `p_holm=0.0078`: hướng kém hơn nhất quán nhưng cỡ hiệu ứng rất nhỏ. `soft_full` cũng kém hơn Standard (+0.918 điểm), Pairwise (+0.836) và CO-QF (+2.254), nhưng tốt hơn HardCluster (−0.692). Các kiểm định này chỉ phản ánh generator synthetic và không ngoại suy thành hiệu quả trên người dùng thật. [Bảng trial](../results/tables/phase2_heldout_synthetic.md) và [bảng kiểm định](../results/tables/phase2_paired_ablation_stats.md).

## Gitcoin background + injected attack

Các số là trung bình ba họ attack trên `42161:865` và `42161:867`, % quỹ nghiên cứu B=USD 100.000. Chúng là mô tả của **hai vòng**, không phải kiểm định độc lập. Vòng `29` chỉ là sensitivity cùng mùa. Với mỗi family/round, năm nhãn seed của brief tạo **cùng một thiết kế tất định**; pipeline chạy một cặp thế giới duy nhất và ghi năm nhãn lặp. Không đếm chúng là năm trial độc lập.

| Cơ chế | Gain 865+867 (% B) ↓ | Gain 29 (% B) ↓ | Tổng chênh lệch tuyệt đối với Standard trên background 865+867 (% B) |
|---|---:|---:|---:|
| Standard QF | 0.291 | 1.133 | 0.0 |
| Pairwise QF | 0.285 | 1.125 | 0.55 |
| CO-QF paper 2025 Alg. 2 | **0.105** | **0.043** | **115.56** |
| HardCluster | 1.347 | 2.345 | 60.20 |
| size_only | 0.634 | 1.581 | 24.53 |
| soft_base | 0.195 | 0.540 | 52.14 |
| soft_shapley | 0.262 | 0.667 | 51.60 |
| soft_centrality | 0.195 | 0.539 | 51.80 |
| soft_full | 0.258 | 0.663 | 51.34 |

Trên empirical, `soft_full` cũng không vượt `soft_base` về gain trung bình. Con số chênh lệch background có thể vượt 100% B vì đây là **tổng độ lệch tuyệt đối** của phân bổ (hai phía được cộng), tối đa 200% B. Nó không phải `MechDamage` và không chứng minh dự án nền là sạch. Attack spillover giữa hai thế giới và tất cả chỉ số theo trial nằm trong [bảng empirical](../results/tables/phase2_heldout_empirical.md).

## Biểu đồ và giới hạn

- [Trade-off frontier trên dev](../results/figures/fig01_tradeoff_frontier_dev.png)
- [Synthetic held-out ablation](../results/figures/fig02_heldout_synthetic_ablation.png)
- [Gitcoin held-out và sensitivity](../results/figures/fig03_heldout_empirical_gitcoin.png)

Ba PNG có metadata 300 DPI và được dựng từ CSV đã lưu. Có bốn giới hạn nghiên cứu chính: (1) synthetic generator có thể bỏ sót hành vi thực; (2) Gitcoin background không có nhãn Sybil, nên `DiffVsStandard` không phải phạt oan định lượng; (3) các kịch bản empirical cố định không tạo năm phép lặp độc lập dù có năm seed label; (4) chọn cấu hình Dev không ổn định trước sai số số học gần 0 như đã kiểm toán. Riêng `coqf_paper2025_alg2` là bản paper 2025, không phải Gitcoin Markov 2024. Phase 2 vì thế **không xác nhận** giả thuyết rằng kết hợp Louvain–Shapley–Centrality vượt các nhánh đơn giản hơn. Kết quả là cơ sở để kiến trúc sư quyết định luận điểm khoa học trước Giai đoạn 3; chưa có cơ sở tuyên bố cơ chế sẵn sàng phân bổ quỹ thật.

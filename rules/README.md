# 📘 Rules Engine – Bộ quy tắc cảnh báo E-code

File `risk_rules.yaml` định nghĩa các điều kiện và mức cảnh báo dựa trên:
- Mã phụ gia (E-code)
- Nhóm chức năng (Category)
- Mức ADI (mg/kg thể trọng/ngày)
- Quốc gia bị cấm
- Tác dụng phụ (Effects)

### Mức cảnh báo
| RiskLevel | Ý nghĩa |
|------------|----------|
| Safe | Có thể sử dụng trong giới hạn cho phép |
| Caution | Cần thận trọng, tránh lạm dụng |
| Avoid | Không nên dùng / bị cấm tại nhiều quốc gia |

Hệ thống sẽ kiểm tra các quy tắc **theo thứ tự ưu tiên** (trên cùng được kiểm tra trước).

# 📘 Mapping CSV → Ontology

| CSV Column         | Ontology Node            | Relation        | Ghi chú |
|--------------------|--------------------------|-----------------|----------|
| ECode              | Additive                 | -               | Mã phụ gia duy nhất |
| Category           | Category                 | HAS_CATEGORY    | Nhóm chức năng (Colorant, Preservative,...) |
| RiskLevel          | RiskLevel                | HAS_RISK        | Mức độ an toàn |
| Effects            | Effect                   | HAS_EFFECT      | Danh sách tác hại, phân tách bằng dấu phẩy |
| BannedIn           | Country                  | BANNED_IN       | Quốc gia hoặc khu vực cấm sử dụng |
| ADI_mgkg           | Thuộc tính của Additive  | -               | Lượng cho phép (mg/kg thể trọng/ngày) |
| CommonName         | Thuộc tính của Additive  | -               | Tên thường gọi  |
| Contraindications  | Thuộc tính của Additive  | -               | Chống chỉ định  |
| Source             | Source                   | -               | Tên thường gọi  |


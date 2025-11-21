# Mapping CSV → Ontology (INS Dataset)

## 1. Thuộc tính trực tiếp của node Additive
| CSV Column | Additive Property | Ghi chú |
|-----------|-------------------|---------|
| ins       | ins               | Mã INS duy nhất |
| name      | name              | Tên tiếng Anh |
| name_vn   | name_vn           | Tên tiếng Việt |
| adi       | adi               | Acceptable Daily Intake |
| info      | info              | Thông tin mô tả |

Node Additive:
(Additive { ins, name, name_vn, adi, info })

---

## 2. Thuộc tính dạng danh sách + node riêng
### FUNCTION
| CSV Column | Ontology Node | Relation |
|------------|----------------|----------|
| function   | Function       | HAS_FUNCTION |

- Một Additive có thể có nhiều Function
- CSV có thể phân tách bởi dấu “,” hoặc “.”

---

### STATUS (trạng thái sử dụng tại VN)
| CSV Column | Ontology Node | Relation |
|------------|----------------|----------|
| status_vn  | Status         | HAS_STATUS |

---

### RISK LEVEL
| CSV Column | Ontology Node | Relation |
|------------|----------------|----------|
| level      | RiskLevel      | HAS_RISK |
- Giá trị:
- 1 ~ vs  (Very Safe)
- 2 ~ sl  (Safe w/ Limits)
- 4 ~ bt  (Banned/Toxic)

---

### SOURCE
| CSV Column | Ontology Node | Relation |
|------------|----------------|----------|
| source     | Source         | HAS_SOURCE |
- Mỗi nguồn thông tin được tạo thành node riêng.

---

## 3. Cấu trúc tổng quát

(Additive)-[:HAS_FUNCTION]->(Function)
(Additive)-[:HAS_STATUS]->(Status)
(Additive)-[:HAS_RISK]->(RiskLevel)
(Additive)-[:HAS_SOURCE]->(Source)
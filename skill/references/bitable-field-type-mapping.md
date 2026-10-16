# Bitable API 字段类型映射

飞书 Bitable API 返回的字段类型代码与配置文件中的类型名称对应关系：

| API 类型代码 | 配置类型名称 | 说明 |
|-------------|-------------|------|
| 1005 | AutoNumber | 自动编号（编码字段） |
| 1 | Text | 文本字段 |
| 1001 | CreatedTime | 创建时间 |
| 2 | Number | 数字字段 |
| 20 | Formula | 公式字段（自动计算） |

## 标准字段模板

大多数计件群使用相同的字段结构和 field_id：

```json
{
  "编码": {"field_id": "fld_<redacted-01>", "type": "AutoNumber", "is_primary": true},
  "姓名": {"field_id": "fld_<redacted-02>", "type": "Text"},
  "日期/时间": {"field_id": "fld_<redacted-03>", "type": "CreatedTime", "formatter": "yyyy/MM/dd HH:mm"},
  "单价": {"field_id": "fld_<redacted-04>", "type": "Number", "formatter": "0.000"},
  "数量": {"field_id": "fld_<redacted-05>", "type": "Number", "formatter": "0"},
  "金额": {"field_id": "fld_<redacted-06>", "type": "Formula", "formatter": "0.00", "auto_calculated": true},
  "审核状态": {"field_id": "fld_<redacted-07>", "type": "Text"},
  "审核人": {"field_id": "fld_<redacted-08>", "type": "Text"},
  "备注": {"field_id": "fld_<redacted-09>", "type": "Text"}
}
```

## 注意事项

- 新表格可能使用不同的 field_id，必须通过 API 验证
- 公式字段（金额）的 `auto_calculated: true` 表示由飞书自动计算
- CreatedTime 字段的 formatter 必须与飞书设置一致

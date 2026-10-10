# 评论数据缺失根因诊断

## 1. note.json 的 source 标记

- `browser_dom`：**27** 篇，其中 20 篇恰好 10 条评论
- `(无source 字段)`：**15** 篇，其中 0 篇恰好 10 条评论

## 2. 核心字段：key 不存在 vs 值为空

这是判定的关键 —— 两者含义完全不同。

| source | 笔记数 | 评论数 | key缺失 | 值为空 | 有真实值 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `(无source)` | 13 | 645 | 4 | 512 | 2064 |
| `browser_dom` | 25 | 230 | 230 | 690 | 0 |

> 每条评论贡献 4 个字段（4 个核心字段 × 评论数= 总检查数）

## 3. 抽样对比原始记录

### source=`(无source)` — `6931e77a`（5 条）

```json
{
  "at_users": [],
  "content": "为什么有的kao旁边有月亮，有的没有月亮，有什么区别吗？",
  "create_time": 1772806441000,
  "id": "69aae1290000000014032d90",
  "invalid": false,
  "ip_location": "江苏",
  "like_count": "2",
  "liked": false,
  "note_id": "6931e77a000000001e033f7b",
  "show_tags": [],
  "status": 0,
  "sub_comment_count": "4",
  "sub_comment_cursor": "69b139610000000015008eea",
  "sub_comment_has_more": true,
  "sub_comments": [
    {
      "user_info": {
        "ai_agent": false,
        "xsec_token": "AB5JGMLRR6yPtGtpGURJ7VDr2YDPevkDsTxoaBhMcQuRw=",
        "user_id": "656d5cb9000000002003611a",
        "nickname": "喜楽",
        "image": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo31sfgot1ilm005pbdbiso6o8qe65h7kg?imageView2/2/w/120/format/jpg"
      },
      "show_tags": [],
      "target_comment": {
        "id": "69aae1290000000014032d90",
        "user_info": {
          "image": "https://sns-avatar-qc.xhscdn.com/avatar/5aca016de8ac2b7458dc9843.jpg?imageView2/2/w/120/format/jpg",
          "ai_agent": false,
          "xsec_token": "ABvYuqBCPMs2f3LvV8gNM7G_aTgoU-kBMbAhhl9NltvJw=",
          "user_id": "5aca016de8ac2b7458dc9843",
          "nickname": "Remember"
        }
      },
 
```

- `create_time` → ✅ 有值 `1772806441000`
- `ip_location` → ✅ 有值 `江苏`
- `like_count` → ✅ 有值 `2`
- `user_info` → ✅ 有值 `{'xsec_token': 'ABvYuqBCPMs2f3LvV8gNM7G_aTgoU-kBMbAhhl9NltvJ...`

### source=`browser_dom` — `693abce3`（10 条）

```json
{
  "_is_reply": false,
  "content": "我觉得它最厉害的是抗氧化",
  "id": "693e31b1000000003800d096",
  "ip_location": "",
  "like_count": "0",
  "pictures": [],
  "sub_comment_count": 0,
  "user_info": {}
}
```

- `create_time` → **key 不存在**
- `ip_location` → ❌ 空 ``
- `like_count` → ❌ 空 `0`
- `user_info` → ❌ 空 `{}`

## 4. 结论

### `(无source)`

- key 缺失率 **0.2%**，真实值率 **80.0%**
- → 混合情况

### `browser_dom`

- key 缺失率 **25.0%**，真实值率 **0.0%**
- → 混合情况

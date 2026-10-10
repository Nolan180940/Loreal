# 匿名取 token 可行性验证

## 1. 预热

- warmup(): **True**
- 当前 URL: `https://www.xiaohongshu.com/login?redirectPath=http%3A%2F%2Fwww.xiaohongshu.com%2Fexplore%3Fchannel_id%3Dhomefeed_recommend%26exSource%3Dnull`
- cookie: `a1, abRequestId, acw_tc, acw_tc, ets, gid, loadts, sec_poison_id, webBuild, webId, web_session, websectiga, xsecappid`

## 2. 从推荐流提取 (note_id, xsec_token)

```
{
 "keys": [
  "query",
  "isFetching",
  "isError",
  "feedsWrapper",
  "undertakeNote",
  "undertakeNoteError",
  "feeds",
  "currentChannel",
  "unreadInfo",
  "validIds",
  "mfStatistics",
  "channels",
  "isResourceDisplay",
  "isActivityEnd",
  "cancelFeedRequest",
  "prefetchId",
  "mfRequestMetaData",
  "placeholderFeeds",
  "feedsCacheLogInfo",
  "isUsingPlaceholderFeeds",
  "placeholderFeedsConsumed",
  "isReplace",
  "isFirstSuccessFetched",
  "imgNoteFilterStatus",
  "ssrRequestStatus",
  "ssrRenderExtra",
  "undertakeNoteOpen",
  "undertakeNoteId",
  "undertakeXsecToken",
  "undertakeNotePresented",
  "isUndertakeScene",
  "lastClosedUndertakeNoteIdForPageEnd",
  "exploreVisibleStartTime",
  "exploreNoteOverlayOpen"
 ],
 "isArray": true,
 "len": 0,
 "sample": null
}
```

## 3. 直接从 DOM 抓推荐卡片链接

```
(0 个链接)
```

## 4. 用推荐流的 token 打开详情页

拿到 **0** 个带 token 的链接

**推荐流也拿不到 token，匿名路径基本断了。**
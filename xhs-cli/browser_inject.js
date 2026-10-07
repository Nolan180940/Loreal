/**
 * 浏览器侧采集脚本（注入到页面上下文，跨导航常驻）。
 *
 * 用法（在 VS Code integrated browser 的 Playwright 通道里）：
 *   await context.addInitScript(fsContent)
 *   然后 page.goto(url) -> page.evaluate(() => window.__XHS_PUSH__())
 *
 * 为什么必须用 addInitScript：
 *   window 上挂的函数在 page.goto 后随文档上下文一起销毁，
 *   批量导航时每个页面都得重新装一遍，��能只装一次。
 *
 * 暴露两个函数：
 *   __XHS_EXTRACT__()  纯提取，不发请求（调试用）
 *   __XHS_PUSH__()     提取 + POST 到本地 recv_server
 */
(() => {
  if (window.__XHS_EXTRACT__) return;   // 幂等，避免重复注入

  window.__XHS_EXTRACT__ = function () {
    const s = window.__INITIAL_STATE__;
    if (!s) return { error: 'no_state', url: location.href };
    const map = s.note && s.note.noteDetailMap;
    if (!map) return { error: 'no_map', url: location.href };
    const keys = Object.keys(map);
    if (!keys.length || keys[0] === 'undefined') {
      return { error: 'bad_key', keys: keys, url: location.href };
    }
    const d = map[keys[0]] || {};
    const n = d.note || {};
    const u = n.user || {};
    const ii = n.interactInfo || {};
    const cs = d.comments || {};

    const images = (n.imageList || []).map(function (im, i) {
      return {
        idx: i,
        url: im.urlDefault || im.url || '',
        w: im.width || 0,
        h: im.height || 0
      };
    }).filter(function (x) { return x.url; });

    const out = [];
    (cs.list || []).forEach(function (c) {
      out.push({
        id: c.id,
        content: c.content || '',
        create_time: c.create_time,
        ip_location: c.ip_location || '',
        like_count: String(c.like_count != null ? c.like_count : '0'),
        user_info: c.user_info ? {
          user_id: c.user_info.userId || c.user_info.user_id || '',
          nick_name: c.user_info.nickname || c.user_info.nickName || '',
          image: c.user_info.image || ''
        } : {},
        sub_comment_count: c.sub_comment_count || 0,
        pictures: [],
        _is_reply: false
      });
      (c.sub_comments || []).forEach(function (r) {
        out.push({
          id: r.id,
          content: r.content || '',
          create_time: r.create_time,
          ip_location: r.ip_location || '',
          like_count: String(r.like_count != null ? r.like_count : '0'),
          user_info: r.user_info ? {
            user_id: r.user_info.userId || r.user_info.user_id || '',
            nick_name: r.user_info.nickname || r.user_info.nickName || '',
            image: r.user_info.image || ''
          } : {},
          sub_comment_count: 0,
          pictures: [],
          _is_reply: true,
          _parent_id: c.id
        });
      });
    });

    const s2 = (v) => String(v != null ? v : '');
    return {
      note_id: keys[0],
      note: {
        title: n.title || '',
        desc: n.desc || '',
        tags: (n.tagList || []).map(function (t) { return t.name || ''; }).filter(Boolean),
        author: u.nickName || u.nickname || '',
        author_id: u.userId || u.user_id || '',
        author_link: u.userId
          ? 'https://www.xiaohongshu.com/user/profile/' + u.userId : '',
        link: location.href,
        type: n.type === 'video' ? '视频' : '图文',
        time_ms: n.time || null,
        ip_location: n.ipLocation || '',
        liked: s2(ii.likedCount),
        collected: s2(ii.collectedCount),
        comment_count: s2(ii.commentCount),
        share_count: s2(ii.shareCount)
      },
      images: images,
      comments: out,
      pages: 1,
      hasMore: !!cs.hasMore,
      cursor: cs.cursor || null,
      source: 'browser_dom'
    };
  };

  window.__XHS_PUSH__ = async function () {
    const d = window.__XHS_EXTRACT__();
    if (d.error) return d;
    try {
      const r = await fetch('http://127.0.0.1:8765/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(d)
      });
      const txt = await r.text();
      let j;
      try { j = JSON.parse(txt); } catch (_) { j = { raw: txt.slice(0, 200) }; }
      return {
        pushed: r.ok, status: r.status, server: j,
        id: d.note_id, imgs: d.images.length, cmts: d.comments.length
      };
    } catch (e) {
      return { pushed: false, err: String(e) };
    }
  };

  /**
   * 拉取评论（走 comment/page API，不是 SSR）。
   *
   * 为什么要单独做：SSR 的 comments.list **不含** user_info / ip_location /
   * create_time —— 实测 25 篇笔记的 230 条评论这三个字段全是空的，
   * 而走 API 的历史数据 645/645 完整。只有 API 才有完整评论。
   *
   * 同时支持翻页：匿名状态下第 2 页必 461，但登录态可用。
   * cursor 与签发会话绑定，所以整个翻页过程必须在同一页面上下文里完成。
   *
   * 用法：await window.__XHS_FETCH_COMMENTS__(noteId, cursor, maxPages)
   */
  window.__XHS_FETCH_COMMENTS__ = async function (noteId, cursor, maxPages) {
    maxPages = maxPages || 1;
    const acc = [];
    let cur = cursor || '';
    let pages = 0;
    let hasMore = true;

    while (pages < maxPages && hasMore) {
      const body = {
        note_id: noteId,
        cursor: cur,
        top_comment_id: '',
        image_formats: ['jpg', 'webp', 'avif'],
        xsec_token: (location.search.match(/xsec_token=([^&]+)/) || [])[1] || ''
      };
      let j;
      try {
        const r = await fetch('/api/sns/web/v2/comment/page', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json;charset=UTF-8' },
          body: JSON.stringify(body)
        });
        if (r.status === 461) {
          return { error: 'risk_461', pages: pages, got: acc.length, comments: acc };
        }
        j = await r.json();
      } catch (e) {
        return { error: 'net:' + String(e).slice(0, 80), pages: pages,
                 got: acc.length, comments: acc };
      }
      if (!j || j.success !== true || !j.data) {
        return { error: 'bad_resp:' + JSON.stringify(j || {}).slice(0, 140),
                 pages: pages, got: acc.length, comments: acc };
      }
      const list = j.data.comments || [];
      acc.push.apply(acc, list.map(function (c) {
        const ui = c.user_info || {};
        return {
          id: c.id,
          content: c.content || '',
          create_time: c.create_time,
          ip_location: c.ip_location || '',
          like_count: String(c.like_count != null ? c.like_count : '0'),
          user_info: {
            user_id: ui.user_id || ui.userId || '',
            nickname: ui.nickname || ui.nickName || '',
            image: ui.image || ''
          },
          sub_comment_count: c.sub_comment_count || 0,
          sub_comment_cursor: c.sub_comment_cursor || '',
          sub_comment_has_more: !!c.sub_comment_has_more,
          pictures: (c.pictures || []).map(function (p) {
            return p.url_default || p.urlDefault || '';
          }),
          liked: !!c.liked,
          show_tags: c.show_tags || [],
          _is_reply: false
        };
      }));
      pages += 1;
      hasMore = !!j.data.has_more;
      const next = j.data.cursor || '';
      if (!next || next === cur) break;   // cursor 没变 = 翻页失效，别死循环
      cur = next;
      await new Promise(function (r) { setTimeout(r, 1200); });
    }
    return { comments: acc, pages: pages, hasMore: hasMore, cursor: cur };
  };
})();
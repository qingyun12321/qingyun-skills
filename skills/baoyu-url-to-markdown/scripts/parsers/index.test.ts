import { describe, expect, test } from "bun:test";

import {
  createMarkdownDocument,
  extractMetadataFromHtml,
} from "../markdown-conversion-shared.js";
import { tryUrlRuleParsers } from "./index.js";

const CAPTURED_AT = "2026-03-22T06:00:00.000Z";

const ARTICLE_HTML = `<!doctype html>
<html lang="zh-CN">
  <body>
    <div data-testid="twitterArticleReadView">
      <a href="/dotey/article/2035141635713941927/media/1">
        <div data-testid="tweetPhoto">
          <img src="https://pbs.twimg.com/media/article-cover.jpg" alt="Image">
        </div>
      </a>
      <div data-testid="twitter-article-title">Karpathy："写代码"已经不是对的动词了</div>
      <div data-testid="User-Name">
        <a href="/dotey">宝玉 Verified account</a>
        <a href="/dotey">@dotey</a>
        <time datetime="2026-03-20T23:49:11.000Z">Mar 20</time>
      </div>
      <div data-testid="twitterArticleRichTextView">
        <p>Andrej Karpathy 说他从 2024 年 12 月起就基本没手写过一行代码。</p>
        <a href="/dotey/article/2035141635713941927/media/2">
          <div>
            <div>
              <div data-testid="tweetPhoto">
                <img src="https://pbs.twimg.com/media/article-inline.jpg" alt="Image">
              </div>
            </div>
          </div>
        </a>
        <h2>要点速览</h2>
        <ul>
          <li>核心焦虑从 GPU 利用率转向 Token 吞吐量</li>
        </ul>
        <blockquote>
          <p>写代码已经不是对的动词了。</p>
        </blockquote>
      </div>
    </div>
  </body>
</html>`;

const STATUS_HTML = `<!doctype html>
<html lang="en">
  <body>
    <article data-testid="tweet">
      <div data-testid="User-Name">
        <a href="/dotey">宝玉 Verified account</a>
        <a href="/dotey">@dotey</a>
        <time datetime="2026-03-22T05:33:00.000Z">Mar 22</time>
      </div>
      <div data-testid="tweetText">
        <span>转译：把下面这段加到你的 Codex 自定义指令里，体验会好太多：</span>
      </div>
      <div data-testid="tweetPhoto">
        <img src="https://pbs.twimg.com/media/tweet-main.jpg" alt="Image">
      </div>
      <div data-testid="User-Name">
        <a href="/mattshumer_">Matt Shumer Verified account</a>
        <a href="/mattshumer_">@mattshumer_</a>
        <time datetime="2026-03-17T00:00:00.000Z">Mar 17</time>
      </div>
      <div data-testid="tweetText">
        <span>Add this to your Codex custom instructions for a way better experience.</span>
      </div>
    </article>
  </body>
</html>`;

const ARCHIVE_HTML = `<!doctype html>
<html>
  <head>
    <title>archive.ph</title>
  </head>
  <body>
    <form>
      <input
        type="text"
        name="q"
        value="https://www.newscientist.com/article/2520204-major-leap-towards-reanimation-after-death-as-mammals-brain-preserved/"
      >
    </form>
    <div id="HEADER">
      Archive shell text that should be ignored when CONTENT exists.
    </div>
    <div id="CONTENT">
      <h1>Major leap towards reanimation after death as mammal brain preserved</h1>
      <p>
        Researchers say the preserved structure and activity markers suggest a significant step
        forward in keeping delicate brain tissue viable after clinical death.
      </p>
      <p>
        The archive wrapper should not take precedence over the actual article body when the
        CONTENT container is available for parsing.
      </p>
      <img src="https://cdn.example.com/brain.jpg" alt="Brain tissue">
    </div>
  </body>
</html>`;

const ARCHIVE_FALLBACK_HTML = `<!doctype html>
<html>
  <head>
    <title>archive.ph</title>
  </head>
  <body>
    <input type="text" name="q" value="https://example.com/fallback-story">
    <main>
      <h1>Fallback body parsing still works</h1>
      <p>
        When CONTENT is absent, the parser should fall back to the body content instead of
        returning null or keeping the archive wrapper as the final URL.
      </p>
      <p>
        This ensures archived pages with slightly different layouts still produce usable markdown.
      </p>
    </main>
  </body>
</html>`;

function parse(html: string, url: string) {
  const baseMetadata = extractMetadataFromHtml(html, url, CAPTURED_AT);
  return tryUrlRuleParsers(html, url, baseMetadata);
}

describe("url rule parsers", () => {
  test("parses archive.ph pages from CONTENT and restores the original URL", () => {
    const result = parse(ARCHIVE_HTML, "https://archive.ph/SMcX5");

    expect(result).not.toBeNull();
    expect(result?.conversionMethod).toBe("parser:archive-ph");
    expect(result?.metadata.url).toBe(
      "https://www.newscientist.com/article/2520204-major-leap-towards-reanimation-after-death-as-mammals-brain-preserved/"
    );
    expect(result?.metadata.title).toBe(
      "Major leap towards reanimation after death as mammal brain preserved"
    );
    expect(result?.metadata.coverImage).toBe("https://cdn.example.com/brain.jpg");
    expect(result?.markdown).toContain("Researchers say the preserved structure");
    expect(result?.markdown).toContain("![Brain tissue](https://cdn.example.com/brain.jpg)");
    expect(result?.markdown).not.toContain("Archive shell text that should be ignored");
  });

  test("falls back to body when archive.ph CONTENT is missing", () => {
    const result = parse(ARCHIVE_FALLBACK_HTML, "https://archive.ph/fallback");

    expect(result).not.toBeNull();
    expect(result?.conversionMethod).toBe("parser:archive-ph");
    expect(result?.metadata.url).toBe("https://example.com/fallback-story");
    expect(result?.metadata.title).toBe("Fallback body parsing still works");
    expect(result?.markdown).toContain("When CONTENT is absent");
  });

  test("parses X article pages from HTML", () => {
    const result = parse(
      ARTICLE_HTML,
      "https://x.com/dotey/article/2035141635713941927"
    );

    expect(result).not.toBeNull();
    expect(result?.conversionMethod).toBe("parser:x-article");
    expect(result?.metadata.title).toBe("Karpathy：\"写代码\"已经不是对的动词了");
    expect(result?.metadata.author).toBe("宝玉 (@dotey)");
    expect(result?.metadata.coverImage).toBe("https://pbs.twimg.com/media/article-cover.jpg");
    expect(result?.metadata.published).toBe("2026-03-20T23:49:11.000Z");
    expect(result?.metadata.language).toBe("zh");
    expect(result?.markdown).toContain("## 要点速览");
    expect(result?.markdown).toContain(
      "[![](https://pbs.twimg.com/media/article-inline.jpg)](/dotey/article/2035141635713941927/media/2)"
    );
    expect(result?.markdown).toContain("写代码已经不是对的动词了。");

    const document = createMarkdownDocument(result!);
    expect(document).toContain("# Karpathy：\"写代码\"已经不是对的动词了");
  });

  test("parses X status pages from HTML without duplicating the title heading", () => {
    const result = parse(
      STATUS_HTML,
      "https://x.com/dotey/status/2035590649081196710"
    );

    expect(result).not.toBeNull();
    expect(result?.conversionMethod).toBe("parser:x-status");
    expect(result?.metadata.author).toBe("宝玉 (@dotey)");
    expect(result?.metadata.coverImage).toBe("https://pbs.twimg.com/media/tweet-main.jpg");
    expect(result?.metadata.language).toBe("zh");
    expect(result?.markdown).toContain("转译：把下面这段加到你的 Codex 自定义指令里");
    expect(result?.markdown).toContain("> Quote from Matt Shumer (@mattshumer_)");
    expect(result?.markdown).toContain("![");

    const document = createMarkdownDocument(result!);
    expect(document).not.toContain("\n\n# 转译：把下面这段加到你的 Codex 自定义指令里，体验会好太多：\n\n");
  });
});

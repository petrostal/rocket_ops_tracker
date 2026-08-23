import { useState } from 'react';

const URL_PATTERN = /https?:\/\/[^\s<>"']+/gi;
const GYAZO_PATTERN = /^https:\/\/(?:www\.)?gyazo\.com\/([0-9a-f]{32})(?:[/?#].*)?$/i;

interface CommentLink {
  href: string;
  previewUrl: string | null;
}

export function CommentBody({ body }: { body: string }) {
  const links = parseLinks(body);
  const previews = links.filter((link): link is CommentLink & { previewUrl: string } => Boolean(link.previewUrl));
  let cursor = 0;

  return <div className="comment-body">
    <p>{links.map((link, index) => {
      const start = body.indexOf(link.href, cursor);
      const before = body.slice(cursor, start);
      cursor = start + link.href.length;
      return <span key={`${link.href}:${index}`}>{before}<a href={link.href} target="_blank" rel="noreferrer">{link.href}</a></span>;
    })}{body.slice(cursor)}</p>
    {previews.length ? <div className="comment-image-list">{previews.map((link) => <CommentImagePreview key={link.href} link={link} />)}</div> : null}
  </div>;
}

function CommentImagePreview({ link }: { link: CommentLink & { previewUrl: string } }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return <a className="comment-image-preview" href={link.href} target="_blank" rel="noreferrer" aria-label="Открыть изображение из комментария">
    <img src={link.previewUrl} alt="Изображение из комментария" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
  </a>;
}

function parseLinks(body: string): CommentLink[] {
  return [...body.matchAll(URL_PATTERN)].map((match) => {
    const href = trimTrailingPunctuation(match[0]);
    const gyazo = href.match(GYAZO_PATTERN);
    return { href, previewUrl: gyazo ? `https://i.gyazo.com/${gyazo[1]}.png` : null };
  });
}

function trimTrailingPunctuation(value: string): string {
  return value.replace(/[.,!?;:]+$/g, '');
}

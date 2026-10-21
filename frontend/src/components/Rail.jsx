import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icon";

const ITEMS = [
  { id: "intake", icon: "user", title: "Your CV" },
  { id: "momentum", icon: "pulse", title: "Skill momentum" },
  { id: "roles", icon: "list", title: "Roles", needsResults: true },
  { id: "sources", icon: "info", title: "Sources", bottom: true },
];

/** Left icon rail with a sliding glass marker on the section in view. */
export default function Rail({ hasResults }) {
  const [active, setActive] = useState("intake");
  const [y, setY] = useState(0);
  const refs = useRef({});
  const locked = useRef(null); // timer: ignore scroll-spy while a click scrolls the page

  const place = useCallback(() => {
    const el = refs.current[active];
    if (el) setY(el.offsetTop + el.offsetHeight / 2);
  }, [active]);

  useLayoutEffect(() => { place(); }, [place, hasResults]);

  useEffect(() => {
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [place]);

  // scroll-spy: sections crossing a line at 35% of the viewport are "here". Side-by-side
  // sections (CV card and momentum chart on wide screens) both cross it, so the one
  // already active, e.g. the one just clicked, keeps the marker.
  useEffect(() => {
    const ids = ITEMS.filter((i) => !i.needsResults || hasResults).map((i) => i.id);
    const onScroll = () => {
      if (locked.current) return;
      const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      if (atBottom) return setActive(ids[ids.length - 1]);
      const line = window.innerHeight * 0.35;
      const crossing = [];
      let above = ids[0];
      for (const id of ids) {
        const r = document.getElementById(id)?.getBoundingClientRect();
        if (!r) continue;
        if (r.top <= line) above = id;
        if (r.top <= line && r.bottom > line) crossing.push(id);
      }
      setActive((prev) => (crossing.includes(prev) ? prev : crossing.at(-1) ?? above));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [hasResults]);

  const go = (e, item) => {
    e.preventDefault();
    setActive(item.id);
    clearTimeout(locked.current);
    locked.current = setTimeout(() => { locked.current = null; }, 800);
    const el = document.getElementById(item.id);
    if (item.id === "intake") window.scrollTo({ top: 0, behavior: "smooth" });
    else el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <nav className="rail" aria-label="Sections">
      <Icon name="logo" size={36} className="logo" />
      <span className="rail-ind" style={{ transform: `translateY(${y - 26}px)` }} aria-hidden="true" />
      {ITEMS.filter((item) => !item.needsResults || hasResults).map((item) => (
        <a key={item.id} href={`#${item.id}`} ref={(el) => { refs.current[item.id] = el; }}
          className={`${active === item.id ? "on" : ""}${item.needsResults ? " appear" : ""}${item.bottom ? " bottom" : ""}`}
          title={item.title} aria-current={active === item.id ? "location" : undefined}
          onClick={(e) => go(e, item)}>
          <Icon name={item.icon} />
        </a>
      ))}
    </nav>
  );
}

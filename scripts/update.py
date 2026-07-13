#!/usr/bin/env python3
"""
Awesome AI 200 — multilingual auto-updater.

Single source of truth is ``data/repos.json``. This script:

1. Refreshes each repo's **live star count** from the GitHub API and remembers
   the previous value so weekly growth can be shown.
2. Optionally **discovers new rising AI repositories** (recently created,
   fast-growing) and appends them to the dataset.
3. Computes a **Trending** view (biggest weekly movers, or — before any weekly
   history exists — the fastest-growing repos by stars-per-day).
4. Regenerates the README in **6 languages** (English, 简体中文, Español,
   हिन्दी, العربية, فارسی) from the data + localized templates.

Standard library only. Run:  ``GITHUB_TOKEN=<token> python scripts/update.py``
Environment flags:
  AAI_DISCOVER=0   skip discovery of new repos (default: on)
  AAI_SKIP_FETCH=1 skip the live star refresh (render from existing data only)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "repos.json")
OWNER = os.environ.get("GITHUB_REPOSITORY", "morpheusadam/awesome-ai-200")

TRENDING_COUNT = 12
DISCOVER_TOPICS = ["ai-agents", "llm", "agent", "generative-ai", "rag"]
DISCOVER_CREATED_AFTER = "2025-06-01"   # "rising" = created recently
DISCOVER_MIN_STARS = 4000
DISCOVER_MAX_ADD = 15

# --------------------------------------------------------------------------- #
# Languages & localized strings
# --------------------------------------------------------------------------- #
LANGS = [
    {"code": "en", "file": "README.md",       "native": "English",  "flag": "🇬🇧", "rtl": False},
    {"code": "zh", "file": "README.zh-CN.md", "native": "简体中文",  "flag": "🇨🇳", "rtl": False},
    {"code": "es", "file": "README.es.md",    "native": "Español",  "flag": "🇪🇸", "rtl": False},
    {"code": "hi", "file": "README.hi.md",    "native": "हिन्दी",    "flag": "🇮🇳", "rtl": False},
    {"code": "ar", "file": "README.ar.md",    "native": "العربية",  "flag": "🇸🇦", "rtl": True},
    {"code": "fa", "file": "README.fa.md",    "native": "فارسی",    "flag": "🇮🇷", "rtl": True},
]

T = {
    "en": {
        "tagline": "The 200 fastest-rising open-source AI & agent projects on GitHub — auto-ranked from live data, refreshed weekly.",
        "glance_title": "📊 At a glance",
        "repos": "AI & agent repositories, ranked by live GitHub stars",
        "stars": "combined GitHub stars",
        "updated": "Rebuilt automatically — last updated",
        "trending_title": "🔥 Trending now",
        "trending_week": "Biggest star gains since the last weekly update.",
        "trending_velocity": "Fastest-growing projects by stars earned per day since launch.",
        "col_repo": "Repository", "col_stars": "Stars", "col_lang": "Lang",
        "col_desc": "Description", "col_growth": "Growth",
        "full_title": "🏆 The full Top 200",
        "method_title": "📐 Methodology",
        "method_body": "Repositories are drawn from a live GitHub Search across AI/agent topics, restricted to projects created since 2024 (i.e. genuine recent trends, not long-standing giants), and ranked by star count. One obvious star-farmed repo was removed during research. Absolute star counts on GitHub should still be read with some caution.",
        "how_title": "⚙️ How it works",
        "how_body": "All data lives in `data/repos.json`. A weekly GitHub Actions workflow runs `scripts/update.py`, which refreshes every star count, recomputes the trending list, optionally discovers new rising repos, and regenerates this README in every language — so the rankings stay fresh with zero manual work.",
        "contrib_title": "🤝 Contributing",
        "contrib_body": "Suggestions for repos, topics, or new languages are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).",
        "license_note": "Released under the [MIT License](LICENSE). Repository metadata belongs to the respective project owners.",
        "footer": "Built with ❤️ &amp; automated with GitHub Actions",
        "per_day": "/day", "this_week": "this week", "langline": "Read this in:",
    },
    "zh": {
        "tagline": "GitHub 上崛起最快的 200 个开源 AI 与智能体项目 —— 基于实时数据自动排名，每周刷新。",
        "glance_title": "📊 一览",
        "repos": "个 AI 与智能体仓库，按实时 GitHub 星标排名",
        "stars": "累计 GitHub 星标",
        "updated": "自动重建 —— 最近更新",
        "trending_title": "🔥 当前热门",
        "trending_week": "自上次每周更新以来星标增长最多的项目。",
        "trending_velocity": "按发布以来每日新增星标计算，增长最快的项目。",
        "col_repo": "仓库", "col_stars": "星标", "col_lang": "语言",
        "col_desc": "描述", "col_growth": "增长",
        "full_title": "🏆 完整 Top 200",
        "method_title": "📐 方法论",
        "method_body": "仓库来自对 AI/智能体主题的实时 GitHub 搜索，仅限 2024 年后创建的项目（即真正的近期趋势，而非长期巨头），并按星标数排名。研究期间移除了一个明显刷星的仓库。GitHub 上的绝对星标数仍应谨慎看待。",
        "how_title": "⚙️ 工作原理",
        "how_body": "所有数据存放于 `data/repos.json`。每周的 GitHub Actions 工作流运行 `scripts/update.py`，刷新每个星标数、重新计算热门榜、可选地发现新兴仓库，并以每种语言重新生成本 README —— 排名始终保持新鲜，无需人工维护。",
        "contrib_title": "🤝 参与贡献",
        "contrib_body": "欢迎提出仓库、主题或新语言的建议 —— 参见 [CONTRIBUTING.md](CONTRIBUTING.md)。",
        "license_note": "基于 [MIT 许可证](LICENSE) 发布。仓库元数据归各自项目所有者所有。",
        "footer": "用 ❤️ 打造 &amp; 由 GitHub Actions 自动化",
        "per_day": "/天", "this_week": "本周", "langline": "其他语言阅读：",
    },
    "es": {
        "tagline": "Los 200 proyectos de IA y agentes de código abierto que más rápido crecen en GitHub — clasificados automáticamente con datos en vivo, actualizados cada semana.",
        "glance_title": "📊 De un vistazo",
        "repos": "repositorios de IA y agentes, clasificados por estrellas de GitHub en vivo",
        "stars": "estrellas de GitHub combinadas",
        "updated": "Reconstruido automáticamente — última actualización",
        "trending_title": "🔥 Tendencia ahora",
        "trending_week": "Mayores ganancias de estrellas desde la última actualización semanal.",
        "trending_velocity": "Proyectos de más rápido crecimiento por estrellas ganadas al día desde su lanzamiento.",
        "col_repo": "Repositorio", "col_stars": "Estrellas", "col_lang": "Leng.",
        "col_desc": "Descripción", "col_growth": "Crecim.",
        "full_title": "🏆 El Top 200 completo",
        "method_title": "📐 Metodología",
        "method_body": "Los repositorios provienen de una búsqueda en vivo en GitHub sobre temas de IA/agentes, limitada a proyectos creados desde 2024 (es decir, tendencias recientes reales, no gigantes veteranos), y ordenados por número de estrellas. Durante la investigación se eliminó un repositorio con estrellas claramente infladas. Aun así, conviene leer los recuentos absolutos de estrellas con cierta cautela.",
        "how_title": "⚙️ Cómo funciona",
        "how_body": "Todos los datos están en `data/repos.json`. Un flujo de trabajo semanal de GitHub Actions ejecuta `scripts/update.py`, que actualiza cada recuento de estrellas, recalcula la lista de tendencias, descubre opcionalmente nuevos repos en ascenso y regenera este README en todos los idiomas — así el ranking se mantiene fresco sin trabajo manual.",
        "contrib_title": "🤝 Contribuir",
        "contrib_body": "Se agradecen sugerencias de repos, temas o nuevos idiomas — consulta [CONTRIBUTING.md](CONTRIBUTING.md).",
        "license_note": "Publicado bajo la [Licencia MIT](LICENSE). Los metadatos de los repositorios pertenecen a sus respectivos propietarios.",
        "footer": "Hecho con ❤️ y automatizado con GitHub Actions",
        "per_day": "/día", "this_week": "esta semana", "langline": "Léelo en:",
    },
    "hi": {
        "tagline": "GitHub पर सबसे तेज़ी से उभरते 200 ओपन-सोर्स AI और एजेंट प्रोजेक्ट — लाइव डेटा से स्वचालित रैंकिंग, हर सप्ताह अपडेट।",
        "glance_title": "📊 एक नज़र में",
        "repos": "AI और एजेंट रिपॉज़िटरी, लाइव GitHub स्टार के अनुसार रैंक",
        "stars": "कुल GitHub स्टार",
        "updated": "स्वचालित रूप से पुनर्निर्मित — अंतिम अपडेट",
        "trending_title": "🔥 अभी ट्रेंडिंग",
        "trending_week": "पिछले साप्ताहिक अपडेट के बाद सबसे ज़्यादा स्टार बढ़ने वाले।",
        "trending_velocity": "लॉन्च के बाद प्रतिदिन मिले स्टार के हिसाब से सबसे तेज़ बढ़ने वाले प्रोजेक्ट।",
        "col_repo": "रिपॉज़िटरी", "col_stars": "स्टार", "col_lang": "भाषा",
        "col_desc": "विवरण", "col_growth": "वृद्धि",
        "full_title": "🏆 पूरा Top 200",
        "method_title": "📐 पद्धति",
        "method_body": "रिपॉज़िटरी AI/एजेंट टॉपिक्स पर लाइव GitHub सर्च से ली गई हैं, केवल 2024 के बाद बनी परियोजनाओं तक सीमित (यानी असली हालिया ट्रेंड, पुराने दिग्गज नहीं), और स्टार संख्या के अनुसार रैंक। शोध के दौरान एक स्पष्ट रूप से नकली-स्टार वाली रिपॉज़िटरी हटा दी गई। फिर भी GitHub पर पूर्ण स्टार संख्या को थोड़ी सावधानी से पढ़ना चाहिए।",
        "how_title": "⚙️ यह कैसे काम करता है",
        "how_body": "सारा डेटा `data/repos.json` में है। एक साप्ताहिक GitHub Actions वर्कफ़्लो `scripts/update.py` चलाता है, जो हर स्टार संख्या ताज़ा करता है, ट्रेंडिंग सूची पुनः गणना करता है, वैकल्पिक रूप से नई उभरती रिपॉज़ खोजता है, और हर भाषा में यह README फिर से बनाता है — बिना किसी मैनुअल काम के रैंकिंग ताज़ा रहती है।",
        "contrib_title": "🤝 योगदान",
        "contrib_body": "रिपॉज़, टॉपिक या नई भाषाओं के सुझाव सादर आमंत्रित हैं — देखें [CONTRIBUTING.md](CONTRIBUTING.md)।",
        "license_note": "[MIT लाइसेंस](LICENSE) के अंतर्गत जारी। रिपॉज़िटरी मेटाडेटा संबंधित प्रोजेक्ट मालिकों का है।",
        "footer": "❤️ से बनाया गया &amp; GitHub Actions से स्वचालित",
        "per_day": "/दिन", "this_week": "इस सप्ताह", "langline": "इसे यहाँ पढ़ें:",
    },
    "ar": {
        "tagline": "أسرع 200 مشروع ذكاء اصطناعي ووكلاء مفتوح المصدر صعودًا على GitHub — مرتبة تلقائيًا من بيانات حية، وتُحدَّث أسبوعيًا.",
        "glance_title": "📊 لمحة سريعة",
        "repos": "مستودع ذكاء اصطناعي ووكلاء، مرتبة حسب نجوم GitHub الحية",
        "stars": "إجمالي نجوم GitHub",
        "updated": "أُعيد بناؤه تلقائيًا — آخر تحديث",
        "trending_title": "🔥 الرائج الآن",
        "trending_week": "أكبر زيادة في النجوم منذ آخر تحديث أسبوعي.",
        "trending_velocity": "المشاريع الأسرع نموًا حسب النجوم المكتسبة يوميًا منذ الإطلاق.",
        "col_repo": "المستودع", "col_stars": "النجوم", "col_lang": "اللغة",
        "col_desc": "الوصف", "col_growth": "النمو",
        "full_title": "🏆 القائمة الكاملة Top 200",
        "method_title": "📐 المنهجية",
        "method_body": "المستودعات مأخوذة من بحث حي على GitHub في مواضيع الذكاء الاصطناعي/الوكلاء، مقصورة على المشاريع المُنشأة منذ 2024 (أي اتجاهات حديثة حقيقية، لا العمالقة القدامى)، ومرتبة حسب عدد النجوم. أُزيل خلال البحث مستودع واحد ذو نجوم مزيّفة بوضوح. ومع ذلك ينبغي قراءة أعداد النجوم المطلقة على GitHub بشيء من الحذر.",
        "how_title": "⚙️ آلية العمل",
        "how_body": "كل البيانات في `data/repos.json`. يشغّل سير عمل أسبوعي على GitHub Actions الملف `scripts/update.py`، الذي يُحدّث كل عدد نجوم، ويعيد حساب قائمة الرائج، ويكتشف اختياريًا مستودعات صاعدة جديدة، ويعيد توليد هذا الملف بكل اللغات — فتبقى التصنيفات محدّثة دون أي عمل يدوي.",
        "contrib_title": "🤝 المساهمة",
        "contrib_body": "اقتراحات المستودعات أو المواضيع أو اللغات الجديدة مُرحَّب بها — انظر [CONTRIBUTING.md](CONTRIBUTING.md).",
        "license_note": "صادر بموجب [رخصة MIT](LICENSE). بيانات المستودعات مملوكة لأصحاب المشاريع المعنيين.",
        "footer": "صُنع بـ ❤️ وأُتمِت عبر GitHub Actions",
        "per_day": "/يوم", "this_week": "هذا الأسبوع", "langline": "اقرأه بلغتك:",
    },
    "fa": {
        "tagline": "۲۰۰ پروژه‌ی متن‌باز هوش مصنوعی و ایجنت که سریع‌ترین رشد را در گیت‌هاب دارند — رتبه‌بندی خودکار از داده‌ی زنده، به‌روزرسانی هفتگی.",
        "glance_title": "📊 در یک نگاه",
        "repos": "مخزن هوش مصنوعی و ایجنت، رتبه‌بندی‌شده بر اساس ستاره‌ی زنده‌ی گیت‌هاب",
        "stars": "مجموع ستاره‌های گیت‌هاب",
        "updated": "به‌صورت خودکار بازسازی شد — آخرین به‌روزرسانی",
        "trending_title": "🔥 داغِ همین حالا",
        "trending_week": "بیشترین رشد ستاره از آخرین به‌روزرسانی هفتگی.",
        "trending_velocity": "پرشتاب‌ترین پروژه‌ها بر اساس ستاره‌ی کسب‌شده در روز، از زمان انتشار.",
        "col_repo": "مخزن", "col_stars": "ستاره", "col_lang": "زبان",
        "col_desc": "توضیح", "col_growth": "رشد",
        "full_title": "🏆 فهرست کامل Top 200",
        "method_title": "📐 روش‌شناسی",
        "method_body": "مخزن‌ها از جست‌وجوی زنده‌ی گیت‌هاب روی موضوع‌های هوش مصنوعی/ایجنت گرفته شده‌اند، محدود به پروژه‌های ساخته‌شده از ۲۰۲۴ به بعد (یعنی ترندهای واقعیِ اخیر، نه غول‌های قدیمی)، و بر اساس تعداد ستاره مرتب شده‌اند. در جریان تحقیق، یک مخزن با ستاره‌ی آشکارا جعلی حذف شد. با این حال، عدد مطلق ستاره در گیت‌هاب امروز را باید با کمی احتیاط خواند.",
        "how_title": "⚙️ چطور کار می‌کند",
        "how_body": "همه‌ی داده‌ها در `data/repos.json` هستند. یک ورک‌فلوی هفتگی GitHub Actions اسکریپت `scripts/update.py` را اجرا می‌کند که هر تعداد ستاره را تازه می‌کند، فهرست ترند را دوباره حساب می‌کند، به‌اختیار مخزن‌های تازه‌ی روبه‌رشد را کشف می‌کند و این README را به همه‌ی زبان‌ها بازتولید می‌کند — بدون هیچ کار دستی، رتبه‌بندی به‌روز می‌ماند.",
        "contrib_title": "🤝 مشارکت",
        "contrib_body": "پیشنهاد مخزن، موضوع یا زبان جدید خوش‌آمد است — [CONTRIBUTING.md](CONTRIBUTING.md) را ببینید.",
        "license_note": "منتشرشده تحت [مجوز MIT](LICENSE). فراداده‌ی مخزن‌ها متعلق به صاحبان همان پروژه‌هاست.",
        "footer": "ساخته‌شده با ❤️ و خودکارشده با GitHub Actions",
        "per_day": "/روز", "this_week": "این هفته", "langline": "به زبان‌های دیگر:",
    },
}


# --------------------------------------------------------------------------- #
# GitHub API helpers
# --------------------------------------------------------------------------- #
def _get(url: str, token: str | None) -> dict:
    headers = {"User-Agent": "awesome-ai-200-bot", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"_status": 404}
            if exc.code in (403, 429) and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"  rate-limited, sleeping {wait}s...", flush=True)
                time.sleep(wait)
                continue
            print(f"  ! request failed: {exc}", file=sys.stderr)
            return {"_status": exc.code}
        except Exception as exc:  # noqa: BLE001
            print(f"  ! request failed: {exc}", file=sys.stderr)
            return {"_status": -1}
    return {"_status": -1}


def refresh_stars(repos: list[dict], token: str | None) -> None:
    for i, r in enumerate(repos, 1):
        data = _get(f"https://api.github.com/repos/{r['name']}", token)
        if data.get("_status"):
            r["alive"] = False
            continue
        r["prev_stars"] = r.get("stars", data["stargazers_count"])
        r["stars"] = data["stargazers_count"]
        r["forks"] = data.get("forks_count")
        r["language"] = data.get("language")
        r["created_at"] = data.get("created_at")
        r["pushed_at"] = data.get("pushed_at")
        r["alive"] = True
        if r["desc"].get("en") is None and data.get("description"):
            r["desc"]["en"] = data["description"]
        if i % 25 == 0:
            print(f"  refreshed {i}/{len(repos)}", flush=True)
        time.sleep(0.1)


def discover(repos: list[dict], token: str | None) -> int:
    known = {r["name"].lower() for r in repos}
    added = 0
    for topic in DISCOVER_TOPICS:
        if added >= DISCOVER_MAX_ADD:
            break
        q = urllib.parse.quote(f"topic:{topic} created:>{DISCOVER_CREATED_AFTER}")
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=30"
        data = _get(url, token)
        for item in data.get("items", []):
            if added >= DISCOVER_MAX_ADD:
                break
            if item["stargazers_count"] < DISCOVER_MIN_STARS:
                break
            if item["full_name"].lower() in known:
                continue
            known.add(item["full_name"].lower())
            repos.append({
                "rank": None, "name": item["full_name"], "url": item["html_url"],
                "stars": item["stargazers_count"], "prev_stars": item["stargazers_count"],
                "forks": item.get("forks_count"), "language": item.get("language"),
                "created_at": item.get("created_at"), "pushed_at": item.get("pushed_at"),
                "topics": item.get("topics", []), "alive": True, "origin": "discovered",
                "desc": {"en": item.get("description"), "fa": None, "zh": None,
                         "es": None, "hi": None, "ar": None},
            })
            added += 1
        time.sleep(2)
    return added


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def human(n) -> str:
    return f"{n:,}" if isinstance(n, int) else "—"


def age_days(created_at: str | None) -> int:
    if not created_at:
        return 10 ** 6
    try:
        created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return max(1, (datetime.now(timezone.utc) - created).days)
    except Exception:  # noqa: BLE001
        return 10 ** 6


def velocity(r: dict) -> int:
    return int(r.get("stars", 0) / age_days(r.get("created_at")))


def desc_for(r: dict, lang: str) -> str:
    text = r["desc"].get(lang) or r["desc"].get("en") or "—"
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text[:157] + "…" if len(text) > 158 else text


def repo_cell(r: dict) -> str:
    return f"[{r['name']}]({r['url']})"


def lang_switcher(current: str) -> str:
    parts = []
    for lang in LANGS:
        label = f"{lang['flag']} {lang['native']}"
        parts.append(f"**{label}**" if lang["code"] == current
                     else f"[{label}]({lang['file']})")
    return " · ".join(parts)


def badges(total_stars: int, count: int) -> str:
    return " ".join([
        f"![Repositories](https://img.shields.io/badge/repositories-{count}-6f42c1)",
        f"![Total stars](https://img.shields.io/badge/total%20stars-{total_stars // 1000}k%2B-ffd33d)",
        "![Languages](https://img.shields.io/badge/languages-6-0aa)",
        f"[![Weekly update](https://github.com/{OWNER}/actions/workflows/weekly-update.yml/badge.svg)](https://github.com/{OWNER}/actions/workflows/weekly-update.yml)",
        "[![Awesome](https://awesome.re/badge.svg)](https://awesome.re)",
        "![License: MIT](https://img.shields.io/badge/license-MIT-blue)",
    ])


def rtl_open(rtl: bool) -> str:
    return '<div dir="rtl" align="right">\n\n' if rtl else ""


def rtl_close(rtl: bool) -> str:
    return "\n\n</div>" if rtl else ""


def render(lang: dict, repos: list[dict], trending: list[dict],
           use_weekly: bool, stamp: str) -> str:
    code = lang["code"]
    s = T[code]
    rtl = lang["rtl"]
    total_stars = sum(r.get("stars", 0) for r in repos)
    count = len(repos)

    # header cells
    growth_label = s["col_growth"]
    trend_header = (
        f"| # | {s['col_repo']} | {s['col_stars']} | {growth_label} | {s['col_desc']} |\n"
        "|---:|:--|--:|--:|:--|"
    )
    full_header = (
        f"| # | {s['col_repo']} | {s['col_stars']} | {s['col_lang']} | {s['col_desc']} |\n"
        "|---:|:--|--:|:-:|:--|"
    )

    out = []
    out.append("<!-- AUTO-GENERATED — do not edit by hand. Edit data/repos.json or scripts/update.py. -->")
    out.append('<div align="center">')
    out.append("")
    out.append("# 🧠 Awesome AI 200")
    out.append("")
    out.append(f"### {s['tagline']}")
    out.append("")
    out.append(badges(total_stars, count))
    out.append("")
    out.append(f"<sub>{s['langline']}</sub><br>")
    out.append(lang_switcher(code))
    out.append("")
    out.append("</div>")
    out.append("")
    out.append("---")
    out.append("")

    # at a glance
    out.append(rtl_open(rtl) + f"## {s['glance_title']}")
    out.append("")
    out.append(f"- **{count}** {s['repos']}")
    out.append(f"- **{human(total_stars)}** {s['stars']}")
    out.append(f"- 🔄 {s['updated']} **{stamp}**" + rtl_close(rtl))
    out.append("")

    # trending
    out.append(rtl_open(rtl) + f"## {s['trending_title']}")
    out.append("")
    out.append(f"_{s['trending_week'] if use_weekly else s['trending_velocity']}_" + rtl_close(rtl))
    out.append("")
    out.append(trend_header)
    for i, r in enumerate(trending, 1):
        if use_weekly:
            growth = f"+{human(r['stars'] - r['prev_stars'])} {s['this_week']}"
        else:
            growth = f"~{human(velocity(r))}{s['per_day']}"
        out.append(f"| {i} | {repo_cell(r)} | ⭐ {human(r.get('stars', 0))} | {growth} | {desc_for(r, code)} |")
    out.append("")

    # full list
    out.append(f"## {s['full_title']}")
    out.append("")
    out.append(full_header)
    for i, r in enumerate(repos, 1):
        lng = r.get("language") or "—"
        out.append(f"| {i} | {repo_cell(r)} | ⭐ {human(r.get('stars', 0))} | {lng} | {desc_for(r, code)} |")
    out.append("")
    out.append("---")
    out.append("")

    # methodology (collapsible)
    out.append(rtl_open(rtl) + f"<details>\n<summary><b>{s['method_title']}</b></summary>\n\n{s['method_body']}\n\n</details>" + rtl_close(rtl))
    out.append("")
    out.append(rtl_open(rtl) + f"## {s['how_title']}\n\n{s['how_body']}" + rtl_close(rtl))
    out.append("")
    out.append(rtl_open(rtl) + f"## {s['contrib_title']}\n\n{s['contrib_body']}" + rtl_close(rtl))
    out.append("")
    out.append(rtl_open(rtl) + f"## License\n\n{s['license_note']}" + rtl_close(rtl))
    out.append("")
    out.append("---")
    out.append(f'<div align="center"><sub>{s["footer"]}</sub></div>')
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    with open(DATA_PATH, encoding="utf-8") as fh:
        repos = json.load(fh)
    print(f"loaded {len(repos)} repos from data/repos.json")

    if os.environ.get("AAI_SKIP_FETCH") != "1" and token:
        print("refreshing live star counts...")
        refresh_stars(repos, token)
        if os.environ.get("AAI_DISCOVER") != "0":
            print("discovering rising AI repos...")
            n = discover(repos, token)
            print(f"  added {n} new repos")
    else:
        print("skipping live fetch (no token or AAI_SKIP_FETCH=1)")

    # rank by live stars
    repos.sort(key=lambda r: r.get("stars", 0), reverse=True)

    # trending: weekly movers if any, else fastest by velocity
    movers = [r for r in repos if (r.get("stars", 0) - r.get("prev_stars", 0)) > 0]
    use_weekly = len(movers) >= TRENDING_COUNT
    if use_weekly:
        trending = sorted(movers, key=lambda r: r["stars"] - r["prev_stars"], reverse=True)[:TRENDING_COUNT]
    else:
        trending = sorted(repos, key=velocity, reverse=True)[:TRENDING_COUNT]

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for lang in LANGS:
        path = os.path.join(ROOT, lang["file"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(lang, repos, trending, use_weekly, stamp))
        print(f"wrote {lang['file']}")

    with open(DATA_PATH, "w", encoding="utf-8") as fh:
        json.dump(repos, fh, ensure_ascii=False, indent=2)
    print(f"saved data/repos.json ({len(repos)} repos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

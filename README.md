# Tuxscribe

An AI-assisted desktop writing app for novels and long-form non-fiction. Built with GTK3 and OpenRouter.ai.

---

## Features

- **Brief** — Chat with an AI editor to develop your project (premise, characters, world, tone)
- **Writing Examples** — Paste your own prose; Tuxscribe analyses it to build your voice profile
- **Voice Profile** — A generated style guide that governs every AI-drafted chapter
- **Chapter Plan** — Structure your book chapter by chapter, or let the AI map it out
- **Manuscript** — Write chapters with AI (governed by your voice profile), import text, or revise drafts
- **Export** — Export your manuscript as EPUB, DOCX, or PDF

---

## Requirements

- Ubuntu 24.04 / Linux Mint 22.x (or any GTK3-capable Linux)
- Python 3.10+
- An OpenRouter.ai API key (free tier available at [openrouter.ai/keys](https://openrouter.ai/keys))

---

## Installation

### Option 1 — Installer script (recommended)

```bash
cd tuxscribe/
chmod +x install.sh
./install.sh
```

Then launch with:
```bash
tuxscribe
```

Or search for **Tuxscribe** in your application menu.

### Option 2 — Run directly without installing

Install dependencies:

```bash
sudo apt install \
  python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  python3-requests \
  python3-reportlab python3-docx python3-ebooklib
```

Then run:

```bash
cd tuxscribe/
python3 tuxscribe.py
```

---

## First-time setup

1. Launch Tuxscribe
2. Click **⚙ Settings** (top-right)
3. Enter your **OpenRouter API key**
4. Choose a model — Claude 3.5 Sonnet is recommended
5. Click **Save**

---

## Workflow

### 1. Create a project
Click **+ New Project** in the sidebar and give it a name.

### 2. Build your brief
Open the **Brief** tab and talk to your AI editor. Describe your premise, characters, world, and tone. The more detail you provide, the better your drafts will be.

Click **Generate Brief Summary** when you're ready to create a structured summary.

### 3. Add writing examples
Open **Writing Examples** and paste 3–5 pages of your own prose. Click **Analyse Writing Style** to see what Tuxscribe detects. Click **Save Examples**.

### 4. Generate your voice profile
Open **Voice Profile**. Once you have a brief and writing examples, click **Generate Voice Profile**. This profile governs every chapter the AI writes. You can edit it manually.

### 5. Plan your chapters
Open **Chapter Plan**. Click **Generate Plan from Brief** to let the AI structure your book, or click **+ Add Chapter** to build it manually. Each chapter gets a title and synopsis.

### 6. Write
Open **Manuscript**, select a chapter, and click **Write Chapter**. The AI drafts using your brief and voice profile. Use **Revise with AI** to improve a draft, or **Import Text** to load an existing file.

### 7. Export
Open **Export**, set your title and author, choose a format, pick a save folder, and click **Export Manuscript**.

---

## Export formats

| Format | Use case |
|---|---|
| EPUB | E-readers (Kindle, Kobo, Apple Books) |
| DOCX | Microsoft Word, LibreOffice, agents/publishers |
| PDF | Print-ready, sharing |

---

## Recommended models (via OpenRouter)

| Model | Notes |
|---|---|
| `anthropic/claude-3.5-sonnet` | Best overall quality (default) |
| `anthropic/claude-3-opus` | Highest quality, slower |
| `openai/gpt-4o` | Strong alternative |
| `google/gemini-pro-1.5` | Long context window |

---

## Data storage

| Data | Location |
|---|---|
| Projects & content | `~/.local/share/tuxscribe/tuxscribe.db` |
| Settings & API key | `~/.config/tuxscribe/config.json` |

---

## Troubleshooting

**"No module named gi"**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

**Export fails with missing module**
```bash
sudo apt install python3-reportlab python3-docx python3-ebooklib
```

**API errors**
- Check your API key in Settings
- Verify you have credits at [openrouter.ai](https://openrouter.ai)
- Try a different model

**App won't start**
```bash
python3 /opt/tuxscribe/tuxscribe.py
```
Run from terminal to see error messages.

---

## Uninstall

```bash
sudo rm -rf /opt/tuxscribe
sudo rm -f /usr/local/bin/tuxscribe
sudo rm -f /usr/share/applications/tuxscribe.desktop
rm -rf ~/.config/tuxscribe        # removes settings (keeps your writing)
# To also remove your projects:
rm -rf ~/.local/share/tuxscribe
```

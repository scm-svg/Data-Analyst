# Data-Analyst

Static HTML dashboards for data analysis (Chart.js). No build step or Node.js required.

## Clone on your PC

**HTTPS (recommended):**

```bash
git clone https://github.com/scm-svg/Data-Analyst.git
cd Data-Analyst
```

**SSH:**

```bash
git clone git@github.com:scm-svg/Data-Analyst.git
cd Data-Analyst
```

## Run locally

These pages load Chart.js from the CDN, so you need a local web server (opening `file://` links can work but a server is more reliable).

### Option 1: Python (usually preinstalled on macOS/Linux; [install on Windows](https://www.python.org/downloads/))

```bash
python3 -m http.server 8080
```

Then open in your browser:

| Dashboard | URL |
|-----------|-----|
| Main (Bags) | http://localhost:8080/index.html |
| Sportlite | http://localhost:8080/sportlite.html |
| BIOMOVE | http://localhost:8080/BIOMOVE.html |
| Explore Pants | http://localhost:8080/dash_explorepants.html |
| Rio (updated) | http://localhost:8080/Dashboard_Rio_Original_Actualizado%20(1).html |

Press `Ctrl+C` in the terminal to stop the server.

### Option 2: Node.js

```bash
npx --yes serve -p 8080
```

Use the same URLs as above (replace the port if `serve` picks another one).

### Option 3: VS Code / Cursor

Install the **Live Server** extension, open the folder, right-click an HTML file → **Open with Live Server**.

## Requirements

- A modern browser (Chrome, Edge, Firefox, Safari)
- Internet access (Google Fonts and Chart.js load from CDNs)

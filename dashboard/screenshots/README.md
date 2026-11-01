# Power BI dashboard screenshots

Place three **real exports from the completed Power BI report** in this directory.

| Report page | Exact filename |
| --- | --- |
| Market Overview | `market-overview.png` |
| Market Regime Analysis | `market-regimes.png` |
| Risk & Volatility | `risk-volatility.png` |

## Export tips

Open each page in Power BI Desktop, fit the page to the canvas, and capture **only the report canvas** rather than the application's editing panels. Prefer a clear, full-resolution PNG with readable axis labels and titles. Ensure slicers show a sensible default state and no tooltip or selection obscures a chart.

You can save images with the Windows Snipping Tool (Win+Shift+S), then save each PNG with its exact filename above.

The Power BI source project can optionally be placed one folder up as `dashboard/Market-Risk-Analytics.pbix`.

Once the PNGs are in this folder, stage and push them from your local project:

```powershell
git pull
git add dashboard/
git commit -m "Add Power BI dashboard screenshots"
git push
```

**Note:** No screenshot images are supplied by this folder guide; the actual image exports must be added separately.

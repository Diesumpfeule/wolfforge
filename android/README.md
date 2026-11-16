# wolfforge for Firefox on Android

Your wolfforge theme on the phone – as an extension for **Firefox Nightly**.

> ⚠ **Proof of concept, written by Claude (AI) – no warranty, use at your own risk.**
> Not tested on a real phone yet.

Firefox on Android has no `userChrome.css`, no theme API and no way to replace its home page, so
the toolbar and menus of the browser itself **cannot** be themed there. What an extension can do,
wolfforge does:

- **Websites in your colours** – marked text, text cursor, focus outline, scrollbars, checkboxes
  and sliders use your accent colour on every site.
- **Theme packs** for GitHub, Wikipedia and YouTube (the same ones as on the desktop; experimental).
- **Rules for single sites** – *your colours*, *dim*, *invert* (dark mode by force) or *leave
  alone*. Set them from the extension's menu while the site is open.
- **Start page** – ASCII banner and art, clock, search (DuckDuckGo in your colours, or Startpage,
  Brave, SearXNG, Google, Kagi) and your bookmarks; four styles.
- **Themes** – all 23 wolfforge themes, any theme colour as accent, one theme for dark mode and one
  for light mode, and your own themes with a colour picker for all 17 colours.
- **Works with droidforge** – import a theme exported from
  [droidforge](https://github.com/Diesumpfeule/droidforge) or a whole droidforge backup, and the
  browser pages match the launcher. swayforge / wolfforge `.toml` themes import too.
- **Privacy switches** – the *fortress* / *comfort* levels as a list of `about:config` names and
  values (an extension cannot set them for you).
- No data leaves the phone: the extension has no server and makes no network requests of its own.

## Install

The extension is not signed by Mozilla, so it only installs in **Firefox Nightly** (Mozilla allows
turning the signature check off there, not in the normal Firefox).

1. Install *Firefox Nightly* (Play Store, or the F-Droid app *FFUpdater* on a phone without Google).
2. Download `wolfforge-android.xpi` from the
   [android release](https://github.com/Diesumpfeule/wolfforge/releases/tag/android).
3. In Nightly, open `about:config`, search for `xpinstall.signatures.required` and set it to **false**.
4. Menu → Settings → About Firefox Nightly → tap the Firefox logo **five times** (“Debug menu enabled”).
5. Back in Settings, tap **Install extension from file** and pick the downloaded file.

The settings open by themselves after installing. Later: menu → Extensions → wolfforge.

Updating: download the new file and install it the same way; your settings stay.

## Good to know

- Open pages show a change after a reload.
- For dark pages everywhere, also set Firefox → Settings → Customize → Theme to *Dark*.
- Firefox cannot use an extension page as home page. Open the start page from the extension's menu
  and keep the tab, or add it to your shortcuts.
- Permission “Access your data for all websites” is what lets the extension add its styles to pages.
  It reads nothing from them.

## For developers

```
python3 android/build.py     # rebuilds ext/data.json from the desktop themes and site styles, writes dist/*.xpi
node android/test.js         # logic tests
```

`ext/data.json` is generated – change the themes in `wolfforge/data/themes` or the styles in
`wolfforge/templates/sites` and run the build.

# Contributing

Thanks for helping make this the best AI-gateway reference! / 感谢贡献！

## Inclusion criteria

A project belongs on this list if **all** of these hold:

1. It is an actual **gateway, proxy, or router for LLM/agent traffic** — it sits on the
   request path. SDK wrappers, chat UIs, and prompt libraries are out of scope.
2. It is **publicly available** (public repo, or a commercial product with public docs).
3. It is **active within the last 12 months** — or it is historically significant and
   explicitly labeled ⚠️ stale.
4. It does **not** rely on reverse-engineered private APIs or resold stolen quota.

## How to add an entry

1. Pick the section that matches the **user pain point** the project serves best
   (an entry may appear in up to two sections).
2. Follow the entry format:

   ```markdown
   - [Name](https://github.com/owner/repo) <!--s:owner/repo-->⭐ ~1k<!--/s--> — One-sentence description ending with a period.
   ```

   - For non-GitHub/commercial products, omit the star marker.
   - The `<!--s:owner/repo-->…<!--/s-->` marker is refreshed daily by CI — put any
     rough number inside; it will be corrected on the next run.
3. If the project ships releases worth announcing, also add `owner/repo` to
   `data/projects.json` → `release_tracked_repos`.
4. Mirror your change in **both** `README.md` and `README.zh-CN.md` (a rough
   translation is fine — maintainers will polish it).
5. Descriptions must be factual and neutral: what it does, language/license if notable,
   one differentiator. No superlatives from the project's own marketing.

## PR checklist

- [ ] Entry follows the format above, in alphabetical-by-relevance position
- [ ] Added to both language READMEs
- [ ] `python -m unittest discover -s scripts -p 'test_*.py'` passes if you touched scripts
- [ ] One project per PR (easier to review)

## Reporting stale or wrong entries

Open an issue with the project name and evidence (last release date, archived repo,
changed pricing). Mislabeled stale projects are bugs — we'd rather know.

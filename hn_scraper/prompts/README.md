# Prompts

Each prompt is a `.md` file in this directory. The filename
(without extension) is its name.

Load with:

```python
from hn_scraper.prompts import load_prompt

text = load_prompt("extract_job", comment_html="<p>...</p>")
```

Variables use Python `str.format` syntax: `{var_name}`. To include
a literal `{` or `}` in a prompt, double it (`{{` / `}}`).

Prompts are versioned in git like code. Treat changes as you would
any code change: a new prompt or a meaningful edit to an existing
one is its own commit, with a message that explains the WHY.

---
layout: default
title: Journal
---
<section class="hero"><h1>Living Only for Today</h1><p>Day by day, I build, with an AI agent, a system that helps agents run carbon and energy cost operations for a steel and chemicals group. Mistakes and detours included.</p></section>
<ol class="list">{% for p in site.posts %}<li><a href="{{ p.url | relative_url }}"><span class="d">{{ p.date | date: "%m.%d" }}</span><span class="t">{{ p.title }}</span><span class="s">{{ p.summary }}</span></a></li>{% endfor %}</ol>

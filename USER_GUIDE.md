# Swarm AI Simulation — User Guide

This app simulates how **1000 people** might react to a breaking event — a news story, natural disaster, market crash, or viral rumor. Each person in the simulation has their own personality, age, income, media habits, and social connections. You control the event; the app shows you how the crowd responds.

---

## What You Need Before Starting

- **Docker Desktop** installed and running on your machine.
  Download it from: https://www.docker.com/products/docker-desktop
- The `test-1` project folder (the one containing this file).

That's it. No Python installation required.

---

## Starting the App

Open a terminal (Command Prompt or PowerShell on Windows) and run these two commands:

```
cd path\to\test-1
docker compose up dashboard
```

Wait about 30–60 seconds while Docker downloads and installs everything automatically.

When you see a line like:

```
You can now view your Streamlit app in your browser.
```

open your web browser and go to:

**http://localhost:8501**

---

## Using the Dashboard

### Step 1 — Choose an Event Preset (optional)

At the top of the left sidebar, there is an **Event Preset** dropdown. Pick one of the ready-made scenarios:

| Preset               | What it represents                              |
| -------------------- | ----------------------------------------------- |
| **Breaking News**    | A significant news story with mixed credibility |
| **Natural Disaster** | A confirmed, high-severity emergency            |
| **Market Crash**     | An economic shock with low authority response   |
| **Viral Rumor**      | Fast-spreading but barely credible information  |

Selecting a preset automatically fills in all the sliders below it. You can still tweak individual sliders after choosing a preset.

---

### Step 2 — Adjust the Event Parameters

Use the sliders to describe the event:

| Slider                 | What it means                      | Low value →          | High value →                             |
| ---------------------- | ---------------------------------- | -------------------- | ---------------------------------------- |
| **Severity**           | How serious is the event?          | Minor inconvenience  | Catastrophic                             |
| **Believability**      | How credible is the information?   | Wild rumor           | Officially confirmed                     |
| **Spread Speed**       | How fast does the news travel?     | Slow word of mouth   | Instant viral                            |
| **Authority Response** | How strongly do officials respond? | Silent / no guidance | Strong clear action                      |
| **Event Type**         | Category of the event              | —                    | social / disaster / economic / political |

---

### Step 3 — Adjust Simulation Settings

| Setting         | What it does                                             | Default |
| --------------- | -------------------------------------------------------- | ------- |
| **Ticks**       | How many time steps to simulate (more = longer run time) | 100     |
| **Agents**      | How many people to simulate                              | 1 000   |
| **Random Seed** | Change this number to get a different random population  | 42      |

---

### Step 4 — Run the Simulation

Click the **Run Simulation** button. A progress bar will appear. For 1000 agents over 100 ticks, this typically takes **10–30 seconds**.

---

## Reading the Results

Once the simulation finishes, four visualisations appear on the right.

---

### Metric Cards (top row)

Five numbers at a glance — what percentage of the population ended up in the most important states:

| Card               | Meaning                                                          |
| ------------------ | ---------------------------------------------------------------- |
| **Calm**           | Unaffected — never noticed or reacted to the event               |
| **Panic**          | Overwhelmed, acting irrationally out of fear                     |
| **Conspiratorial** | Rejected official explanations, spreading alternative narratives |
| **Comply**         | Followed official guidance                                       |
| **Adapt**          | Proactively changed behaviour in a positive way                  |

---

### Behavior State Proportions Over Time (line chart)

Shows how the crowd's emotional state evolved **tick by tick**.

- A fast rise in **Panic** (red) means the event overwhelmed people quickly.
- A high **Comply** (blue) line means official communication worked.
- A growing **Conspiratorial** (purple) line means distrust is spreading — often seen with low-believability events.
- **Calm** (green) dropping early means the event reached most people fast.

---

### Narrative Sentiment at Final Tick (bar chart)

Shows what _story_ people believe at the end, regardless of how they behaved:

| Narrative          | Meaning                                      |
| ------------------ | -------------------------------------------- |
| **Alarmed**        | Believes the threat is real and severe       |
| **Conspiratorial** | Believes the official story is false         |
| **Neutral**        | Has heard about it but has no strong opinion |
| **Adaptive**       | Sees it as a challenge to work through       |

---

### Final Behavior State Distribution (horizontal bar)

A simple count of all nine possible states at the last tick. Useful for seeing the full picture beyond the top-5 cards.

---

### Social Network Snapshot (graph)

Shows 200 of the most connected people and their social links. Each dot is a person; the colour shows their current state. Clusters of the same colour indicate **social contagion** — groups that pulled each other into the same reaction.

---

## Downloading Your Data

Below the charts there are two download buttons:

- **Download tick-level CSV** — one row per simulation tick, columns for every state percentage. Open in Excel or Google Sheets.
- **Download agent JSON** — one record per person at the final tick, including their personality traits, demographic info, behavior state, and narrative type.

---

## Experiments to Try

| Question                                                 | What to change                                                  |
| -------------------------------------------------------- | --------------------------------------------------------------- |
| Does high authority response reduce panic?               | Drag **Authority Response** from 0.1 to 0.9 and compare panic%  |
| How does a rumor spread differently from confirmed news? | Switch between **Viral Rumor** and **Natural Disaster** presets |
| What if information barely reaches anyone?               | Set **Spread Speed** to 0.1                                     |
| Does a different random population change outcomes?      | Change **Random Seed** and re-run with the same event           |
| What happens over a longer time horizon?                 | Increase **Ticks** to 200 or 300                                |

---

## Stopping the App

Go back to the terminal and press **Ctrl + C**. Then run:

```
docker compose down
```

This cleanly shuts down the container.

---

## Troubleshooting

**The page won't load at http://localhost:8501**
Make sure the terminal shows "You can now view your Streamlit app" before opening the browser. If Docker is still pulling layers, wait a little longer.

**The simulation is very slow**
Reduce **Agents** to 200–500 and **Ticks** to 50 for a quick preview.

**Port 8501 is already in use**
Another application is using that port. Stop it, or change the port in `docker-compose.yml` from `"8501:8501"` to `"8502:8501"` and open http://localhost:8502 instead.

**I want to reset everything**
Run `docker compose down` in the terminal. Your exported files in the `data/` folder are kept on your machine and are not affected.

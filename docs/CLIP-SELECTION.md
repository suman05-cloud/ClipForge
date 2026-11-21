# How ClipForge chooses candidate clips

Updated 19 November 2026. The objective is to help an editor find coherent, useful moments throughout a recording. **An editorial score is not a probability of going viral, a prediction of views or a measured retention score.** ClipForge has no social account connection and no audience analytics.

## Research behind the criteria

YouTube's own creator discussion emphasizes an immediate opening and a compact story or moment for Shorts. This is practical creator advice, not a universal one-second algorithm rule. ClipForge uses it to prefer an opening that quickly tells a new viewer why the next seconds matter. See [YouTube Shorts deep dive](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/).

YouTube's retention guidance recommends matching the opening to the title/thumbnail promise and considering strong later content earlier. It also warns that a spike can mean rewatching because a passage was unclear, not only because it was compelling. Real retention comes from viewers after publication, so ClipForge cannot calculate it from a transcript. See [audience-retention guidance](https://support.google.com/youtube/answer/9314415).

These sources motivate the editorial criteria below. The weights, prompts and filtering rules are this app's implementation choices, not a recovered ScaleReach algorithm or a YouTube ranking formula.

## Pipeline

1. **Read the entire saved transcript.** Preserve stable segment IDs and their original timestamps. Divide content into bounded chunks so later sections are not discarded merely because the model has a small context window.
2. **Summarize chunks, then the recording.** Create local summaries and combine them into global subject, themes and story context. This hierarchical compression lets the model reason about a long recording without putting all raw text in one request. Coverage is about submitted saved text, not proof that every spoken word was transcribed correctly.
3. **Construct candidate windows across the recording.** Python samples starts at subtitle boundaries, roughly half the minimum clip duration apart, including a final viable start. Each start gets shortest, middle and longest valid endings, within the requested range and at most 60 seconds. These windows can cross summary-chunk boundaries. The model reviews candidates in whole-video context and chooses useful points, mini-stories, explanations or concise questions/answers; it does not invent timestamps.
4. **Rank candidates using global context.** Compare relevance, hook, payoff, clarity and self-contained meaning. Prefer variety over several near-duplicates. External topic context is optional and cannot override what the source actually says.
5. **Validate and review.** Resolve segment IDs to real timestamps, enforce duration bounds, remove invalid candidates and reduce overlapping/duplicated selections. Return fewer clips when there are not enough valid choices rather than inventing content. The editor then previews, adjusts framing/captions and exports.

Core summary chunks contain approximately 5,000 characters with up to 800 characters of preceding context. Every saved segment is accounted for before clip selection. Candidate-review prompts use a bounded excerpt (beginning/end when text exceeds 900 characters); the complete candidate text participated in the preceding whole-video summaries, but is not necessarily repeated verbatim during ranking. Large candidate pools use bounded ranking rounds. The API records segment coverage, chunk count, candidate count, reviewed groups, model, source links and warnings.

Global summarization is lossy. Even when all transcript chunks are processed, subtle details can be missed or misinterpreted. The UI should expose coverage/warnings, and manual clipping remains available.

## What makes a useful candidate

| Criterion | Prefer | Avoid |
|---|---|---|
| Opening | An immediate question, clear claim, concrete observation or tension already present in the recording | A long preamble, greeting or unexplained reference |
| Standalone meaning | Enough setup for a viewer who has not seen the full recording | A pronoun, answer or callback whose subject is missing |
| Payoff | A completed answer, actionable takeaway, example or story resolution | Cutting just before the answer or ending mid-sentence |
| Specificity | Concrete details supported by the transcript | Generic filler, invented claims or clickbait promises |
| Faithfulness | Preserved intent, qualifications and context | Misleadingly omitting a caveat or reversing the speaker's meaning |
| Collection quality | Distinct themes and limited overlap | Many clips repeating the same point |

The implemented rubric has four equally weighted dimensions: `hook_clarity`, `standalone_context`, `useful_takeaway`, and `ending_payoff`, each rated 0–5. The displayed score is **5 × their sum**, giving a 0–100 editorial scale. Ranking also considers the whole-video narrative and variety, so final order need not be a numerical score sort. Windows sharing more than 60% of the shorter clip are filtered; fewer than the requested count may remain.

Treat any displayed editorial score as a sorting aid. A strong score can still accompany a poor visual moment, weak delivery, transcription error or audience mismatch because transcript analysis does not observe all of those factors.

## Optional web context

If enabled, Tavily receives a topic query derived from the local summary (up to 200 characters; topics first, summary text as fallback) and returns up to three basic-search snippets/links. It does **not** receive the raw video, audio or complete transcript. Search helps with topic vocabulary and context; it does not establish trending status or future performance. Review source dates and claims. The local model should treat search results as untrusted source text and preserve provenance. Without opt-in there is no search request. Opting in without a configured key produces an actionable error; a search-provider failure produces a warning and selection continues locally. See [Tavily's search contract](https://docs.tavily.com/documentation/api-reference/endpoint/search).

## Editor checklist before download

- Does the first sentence make sense without preceding material?
- Is the claim faithful to the original, including important caveats?
- Does the clip deliver the answer or payoff before its end?
- Are names, numbers, captions and boundaries correct?
- Does the crop keep the relevant person or subject visible?
- Is this materially different from the other selected clips?

The finished MP4 is the authority for timing, framing and caption appearance. Watch it once before manually uploading it.


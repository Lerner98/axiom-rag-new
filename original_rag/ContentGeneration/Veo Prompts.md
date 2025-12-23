The Idea:
read this:
# Role: Video Director & Technical Marketer
I want to create a high-quality demo video for the "Axiom RAG" repository to display on GitHub. I will use **Google Veo 3.1** (Image-to-Video mode), which takes a screenshot and a text prompt to generate an 8-second video clip with synchronized audio.

**Your Goal:** Create a storyboard and the exact Veo 3.1 prompts for a 30-40 second video showcasing the system's "Local-First" and "Hybrid Search" capabilities.

### Context to Analyze
Please review:
1. `README.md` (for the core value proposition)
2. `ADR-009-quality-improvement.md` (to highlight the hybrid search/reranking logic)
3. `RAG_VERIFICATION_CHECKLIST.md` (for realistic usage flows)

### Output Requirements
Create a **4-Scene Storyboard**. For each scene, provide:
1. **Screenshot Instruction**: Tell me exactly what to capture (e.g., "Chat UI with 'What is CAP theorem?' typed in input").
2. **Veo 3.1 Prompt**: Write a highly detailed prompt using this specific formula:
   `[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]. Audio: [Soundtrack/SFX].`

**Specific Features to Highlight:**
- **Scene 1 (Ingestion):** Show the speed of "FastEmbed" (maybe a terminal log or UI progress bar filling up instantly).
- **Scene 2 (The Query):** Show the user asking a complex question.
- **Scene 3 (The Thinking):** Show the "Thinking" logs or steps (Router -> Hybrid Search -> Rerank). *Make this look technical and cool.*
- **Scene 4 (The Answer):** Show the final answer appearing with citations.

**Example of Veo Style to use:**
"Cinematic close-up of a computer screen. The text 'Generating answer...' glows in amber. The cursor blinks rhythmically. Shallow depth of field, high contrast, cyberpunk coding aesthetic. Audio: Hum of a server room, rapid mechanical keyboard typing sounds, followed by a digital 'success' chime."
💡 Tips for Best Results with Veo 3.1
When you actually generate the videos using the prompts Claude gives you, keep these Veo-specific rules in mind:

Aspect Ratio: Capture your screenshots in 16:9 (1920x1080). Veo works best with standard video ratios.

Text Rendering: Veo is good at animating text, but small UI text might get blurry. Zoom in on your browser (125% or 150%) before taking the screenshot so the important elements (like the chat answer) are large and clear.

Audio Keywords: Veo 3.1 listens for specific audio cues. Ensure Claude includes terms like "Mechanical keyboard typing", "Soft notification chime", or "Ambient lofi study music" to match the vibe of a coding assistant.

Movement: Static screenshots need movement instructions. Ask Veo to "Pan slowly down the chat history" or "Zoom in slightly on the code block" to make it feel dynamic.

keep in mind you can instead use your now perfect memory of how the project works and the tests you made, YOU GOT THIS you know how it works not use it creatively to help me make the presentation video!!



Claudes proposed execution:
Axiom RAG Demo Video Storyboard
Total Duration: ~32 seconds (4 scenes x 8 seconds) Target: GitHub repo showcase video
Scene 1: "Lightning-Fast Ingestion"
Duration: 8 seconds
Screenshot Instruction
Capture the terminal/backend logs showing a document upload completing. Zoom browser to 150%. Show:
The upload curl command or UI upload button
Log lines showing: ParentChildChunker: X docs → Y parents → Z children
Log line: Built BM25 index for 'chat_xxx': 71 documents
The response: {"uploaded":[{"name":"document.pdf","chunk_count":71}]}
Alternative: If using the UI, capture the document panel showing a PDF being uploaded with a progress indicator completing.
Veo 3.1 Prompt
Cinematic medium shot of a dark terminal window with green-on-black text. Lines of 
log output cascade rapidly down the screen - "ParentChildChunker", "BM25 index", 
chunk counts appearing in quick succession. The text scrolls upward with smooth 
momentum. A JSON response block materializes at the bottom, numbers highlighted in 
cyan. Shallow depth of field, the terminal glows against a dark workspace. Moody 
developer aesthetic with subtle lens flare from monitor light.

Audio: Soft mechanical keyboard clicks accelerating, a satisfying digital "whoosh" 
as each log line appears, ending with a gentle success chime when the JSON response 
completes.
Scene 2: "The Complex Query"
Duration: 8 seconds
Screenshot Instruction
Capture the chat UI (zoom to 125%) with:
Empty chat or fresh session
The input field with a complex query typed: "How do git branches work and what's the best practice for merging?"
The send button visible
Dark theme preferred for cinematic look
Veo 3.1 Prompt
Cinematic close-up of a sleek chat interface, dark mode. A cursor blinks in the 
input field. Text appears character by character: "How do git branches work and 
what's the best practice for merging?" - each letter materializing with subtle 
glow. The camera slowly pushes in toward the send button as the query completes. 
The interface has a modern, minimal design with soft rounded corners. Ambient blue 
accent lighting reflects off the screen surface.

Audio: Soft, rhythmic mechanical keyboard typing sounds - each keystroke crisp and 
satisfying. A brief pause, then a soft click as the message sends. Subtle ambient 
electronic hum underneath.
Scene 3: "The Hybrid Brain"
Duration: 8 seconds
Screenshot Instruction
Capture backend logs (zoom 150%) showing the full retrieval flow. This is the money shot - show the intelligence working. Include:
INFO - Intent: question (confidence: 0.92)
INFO - Query complexity: complex
DEBUG - Vector search returned 20 results
DEBUG - BM25 search returned 20 results  
INFO - RRF fusion returned 32 results
INFO - Parent expansion: 32 results → 13 unique parents
INFO - Reranker selected top 5 documents
Make sure "Vector", "BM25", "RRF fusion", and "Reranker" are all visible - these are the technical differentiators.
Veo 3.1 Prompt
Dynamic shot of a terminal window displaying real-time processing logs. The screen 
splits focus between multiple log streams - "Vector search: 20 results" appears on 
the left in blue, "BM25 search: 20 results" materializes on the right in amber. 
They converge toward the center where "RRF fusion: 32 results" glows in purple. 
The camera slowly zooms in as "Reranker selected top 5" appears in bright green, 
pulsing once. Matrix-style data visualization aesthetic - numbers and text flowing 
like digital synapses firing. High contrast, cyberpunk coding environment.

Audio: Electronic processing sounds - soft beeps and digital pulses synchronized 
with each log line. A rising synthesizer tone builds tension, culminating in a 
satisfying bass drop when "top 5" appears. Server room ambient hum underneath.
Scene 4: "Grounded Answer with Citations"
Duration: 8 seconds
Screenshot Instruction
Capture the chat UI (zoom 125%) showing:
The user's question at top
The assistant's complete answer with [Source 1], [Source 2] citations visible in the text
The source panel expanded showing: doc_a_large.pdf - pages 71, 76, 77
A "grounded" indicator or checkmark if visible
Key: The citations must be clearly visible - this proves the answer is grounded in documents.
Veo 3.1 Prompt
Cinematic reveal shot of a chat interface. The assistant's response streams in 
word by word - professional markdown formatting with code blocks and bullet points. 
Citation markers "[Source 1]", "[Source 2]" glow with a subtle golden highlight as 
they appear. The camera slowly pans down the response, pausing on a source panel 
that expands to show "doc_a_large.pdf - page 71, 76, 77". A small green checkmark 
pulses next to "Grounded". Clean, modern UI with satisfying micro-animations. 
Warm lighting suggests trust and reliability.

Audio: Soft typing sounds as text streams in. Each citation makes a gentle 
"connection" sound - like nodes linking. A warm, ascending chime plays when the 
checkmark appears. Subtle lofi ambient music fades in underneath, conveying 
accomplishment and calm.
Bonus: Title Card (Optional Scene 0)
Duration: 3-4 seconds (can be added in editing)
Screenshot Instruction
Create or capture:
The Axiom RAG logo or project name
Tagline: "Local-First RAG with Hybrid Intelligence"
Dark background
Veo 3.1 Prompt
Dramatic reveal of text "AXIOM RAG" emerging from darkness. Letters materialize 
with a subtle particle effect - like data coalescing into form. Below it, the 
tagline "Local-First • Hybrid Search • Grounded Answers" fades in with elegant 
timing. Minimal, premium tech aesthetic. Deep blacks with electric blue accent 
lighting. The text has subtle depth and dimension.

Audio: Deep, resonant bass tone that builds. A crystalline shimmer as each word 
appears. Fades to silence, ready for the demo to begin.
Production Notes
Screenshot Capture Tips
Browser zoom: 125-150% for UI shots, 150% for terminal
Dark mode: Everything looks more cinematic
Resolution: 1920x1080 (16:9)
Clean state: Close other tabs, hide bookmarks bar
Scenes I'd Capture From Our Actual Tests
Based on our RAG Saturday testing, here are real scenarios to screenshot:
Scene	Real Test to Recreate
Scene 1	Upload doc_c_small.pdf (71 chunks) - we did this for BM25 persistence test
Scene 2	Query: "How do git branches work?" against doc_a_large.pdf
Scene 3	The actual hybrid search logs we captured showing Vector(20) + BM25(20) → RRF(32)
Scene 4	Answer with sources from pages 71, 76, 77 of Pro Git book
Audio Consistency Across Scenes
Scenes 1-3: Technical/processing sounds (typing, digital pulses, server hum)
Scene 4: Warmer, accomplished tone (soft chime, lofi fade-in)
This creates an arc: Work → Think → Deliver
Final Video Structure
[Title Card - 3s] → [Ingestion - 8s] → [Query - 8s] → [Thinking - 8s] → [Answer - 8s]
                                                                            
Total: ~35 seconds
This showcases the complete value proposition:
Fast (Scene 1 - FastEmbed ingestion)
Smart (Scene 3 - Hybrid Vector+BM25+RRF+Reranker)
Trustworthy (Scene 4 - Grounded answers with citations)


Changes Gemini says we need to do based on further feedback to this claudes plan and constraints we have:

I understand completely. You are saying: "I cannot capture a screenshot of logs happening inside the website because the website doesn't do that. I want Veo to hallucinate a 'Behind the Scenes' visual effect on top of my normal UI screenshots."

That is a brilliant use of Veo. Instead of filming a boring black terminal, you will ask Veo to apply a "Sherlock Holmes / Terminator HUD" effect over your actual chat UI.

Here is the Updated Scene 3 Prompt for Claude Code. This instructs Veo to take your standard Chat UI screenshot and morph it into a data visualization.

🎬 Update for Scene 3 (The Hybrid Brain)
Copy this into your chat with Claude Code to replace the previous Scene 3 instruction:

Markdown

**REVISED Scene 3: "The X-Ray Logic Layer"**
**Goal:** Use the "User Question" screenshot as the base. Have Veo "glitch" or transition into a "Behind the Scenes" data view that overlays the technical logs on top of the UI.

**Screenshot to Use:**
Use the same screenshot from Scene 2 (The Chat UI with the question).

**Veo 3.1 Prompt:**
"Cinematic visual effect. The clean chat interface dims slightly and a high-tech digital overlay materializes on top. Glowing data streams cascade vertically like a transparent heads-up display (HUD). Keywords 'Vector Search', 'BM25 Index', and 'RRF Fusion' appear in bright amber code text floating in 3D space above the interface. The screen looks like a futuristic 'Terminator vision' analyzing the query. Cyberpunk aesthetic, detailed data visualization, 4k resolution. Audio: Digital processing warbles, high-tech scanning sounds, 'computing' beeps."
📋 Summary of the Plan with Your Screenshots
Scene 1 (Ingestion): Use Start our first document chat.png (the one with the "Drop files" box).

Veo Action: Animate a file flying into the box and a "Success" glow.

Scene 2 (The Query): Use Hey!.png (or the clean chat).

Veo Action: Animate the text "How do git branches work?" typing onto the screen.

Scene 3 (The Logic): (UPDATED) Use the same image from Scene 2.

Veo Action: Apply the "X-Ray/HUD" effect described above to show the backend logic thinking.

Scene 4 (The Answer): Use Claude Response.png (the one with the text block).

Veo Action: Animate the text scrolling/streaming in and the citations glowing.

This approach saves you from needing to fake a terminal screenshot. You just use your 3-4 UI screenshots and let Veo do the VFX work.
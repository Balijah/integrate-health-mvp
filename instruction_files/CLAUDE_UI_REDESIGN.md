# CLAUDE.md — UI Redesign: Integrate Health Provider Portal

## Overview

This document instructs Claude Code to replace the existing frontend UI with a new design built in Figma. The new design is a complete visual overhaul of the provider portal: new layout system, new navigation paradigm, new color system, custom typography, and a redesigned patient workflow (speak → summarize → sync).

**Backend is untouched.** All existing API contracts, services, models, and verified phases 1–5 remain fully intact. This plan only modifies the `frontend/` directory.

---

## Design System Reference

Before touching any component, internalize these design tokens. All new code must use them consistently.

### Color Palette
| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#4ac6d6` | Borders, active states, buttons, focus rings |
| Primary hover | `#3ab5c5` | Button hover states |
| Primary light | `#4ac6d6/10` | Active nav item background |
| Primary light bg | `#4ac6d6/20` | Secondary button fill |
| Background | `#f8f9fa` | Page background |
| Card | `#ffffff` | Card/panel backgrounds |
| Foreground | `#1a1a1a` | Primary text |
| Muted text | `#6b7280` | Secondary/placeholder text |
| Border radius (cards) | `rounded-2xl` | All cards, modals, containers |
| Border radius (inputs) | `rounded-xl` | All inputs, buttons |
| Border width (cards) | `border-2 border-[#4ac6d6]` | Featured card borders |
| Border width (subtle) | `border border-[#4ac6d6]` | Secondary card borders |

### Typography
| Element | Font | Style |
|---------|------|-------|
| `h1`, `h2`, `h3`, `h4` | Petrona (serif) | Italic, medium weight |
| Body, labels, buttons | Karla (sans-serif) | Normal weight |
| Placeholders / descriptive text | Karla | Italic, `text-gray-500` |

**Required Google Fonts import** (add to `index.html` or global CSS):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Karla:ital,wght@0,400;0,500;1,400;1,500&family=Petrona:ital,wght@0,400;0,500;1,400;1,500&display=swap" rel="stylesheet">
```

### Motion/Animation
- Use `framer-motion` (already in existing `package.json` as `motion`) for all interactive animations
- Spring transitions: `{ type: "spring", stiffness: 300, damping: 20 }`
- Hover scale: `whileHover={{ scale: 1.02 }}`
- Sidebar collapse: `transition-all duration-300`

---

## New Dependency Requirements

Add these to `frontend/package.json`. All others in the current `package.json` remain.

```json
"motion": "^11.0.0",
"lucide-react": "^0.383.0"
```

> **Note:** The Figma export used `motion` v12 from `motion/react`. Use the `framer-motion` package already referenced in the existing codebase, OR add the `motion` package. Either is acceptable — just be consistent across all new components.

---

## New Project Structure

The following shows only what changes. Everything else in `frontend/src/` stays as-is.

```
frontend/src/
├── index.css                    # UPDATE — add Google Fonts + CSS variables
├── App.tsx                      # UPDATE — wrap with PatientProvider + new router
│
├── assets/
│   └── (logo/gradient images)   # ADD — see Asset Strategy section
│
├── components/
│   ├── Layout/
│   │   └── Layout.tsx           # REPLACE — entirely new sidebar + header design
│   ├── AudioRecorder/
│   │   └── AudioRecorder.tsx    # KEEP — logic preserved, visual updates only
│   ├── NoteEditor/
│   │   └── NoteEditor.tsx       # KEEP — logic preserved, visual updates only
│   └── common/
│       ├── Button.tsx           # UPDATE — apply new design tokens
│       ├── Input.tsx            # UPDATE — apply new design tokens
│       ├── Card.tsx             # UPDATE — apply new design tokens
│       └── Loading.tsx          # KEEP
│
├── pages/
│   ├── Login.tsx                # REPLACE — new design
│   ├── Dashboard.tsx            # REPLACE — new "Home" page design
│   ├── NewVisit.tsx             # REPLACE — "start new session" modal pattern
│   ├── VisitDetail.tsx          # REPLACE — new 3-step speak→summarize→sync workflow
│   ├── NoteEditor.tsx           # UPDATE — integrate into VisitDetail step 2
│   └── PatientsList.tsx         # ADD — new patients grid page
│
├── store/
│   ├── authStore.ts             # KEEP — no changes
│   └── visitStore.ts            # KEEP — no changes
│
├── hooks/
│   ├── useAuth.ts               # KEEP — no changes
│   └── useAudioRecorder.ts      # KEEP — no changes
│
└── types/
    └── index.ts                 # UPDATE — add SyncStatus type
```

---

## Asset Strategy

The Figma export uses Figma-hosted asset references (`figma:asset/...`). These must be replaced with the real asset files that already exist in `frontend/src/assets/`.

### Asset Inventory Step
**Before writing any component code**, run the following to list what's available:
```bash
ls frontend/src/assets/
```

Identify and note the filenames for:
- Full logo (used in sidebar header and login page)
- Compact/icon logo (used in collapsed sidebar)
- Gradient background image (used in hero button, recording button, step progress circles)
- Provider profile photo (used in header avatar)

### Implementation Rule
Import assets using standard relative paths:
```ts
import logoImg from '../assets/logo-full.png';       // adjust filename to match actual file
import compactLogoImg from '../assets/logo-icon.png'; // adjust filename to match actual file
import gradientBg from '../assets/gradient-bg.png';   // adjust filename to match actual file
```

**Do not leave any `figma:asset/...` references in any file.** Every asset reference must be a real import from `frontend/src/assets/`.

### Fallbacks (only if a specific file is genuinely missing)
| Asset | CSS/JSX Fallback |
|-------|-----------------|
| Logo (full) | `<span className="font-heading italic text-xl text-gray-900">integrate health</span>` |
| Logo (compact) | `<span className="font-heading italic text-lg text-gray-900">ih</span>` |
| Gradient background | `style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}` |
| Profile photo | `<div className="w-12 h-12 rounded-full bg-[#4ac6d6]/20 flex items-center justify-center"><User className="w-6 h-6 text-[#4ac6d6]" /></div>` |

---

## Phase A: Global Styles & Fonts

**Files to modify:** `frontend/src/index.css`, `frontend/index.html`

### Tasks

1. Add Google Fonts link tags to `frontend/index.html` `<head>`.

2. Replace the contents of `frontend/src/index.css` with:

```css
@import url('https://fonts.googleapis.com/css2?family=Karla:ital,wght@0,400;0,500;1,400;1,500&family=Petrona:ital,wght@0,400;0,500;1,400;1,500&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --font-sans: 'Karla', sans-serif;
  --font-heading: 'Petrona', serif;
  --background: #f8f9fa;
  --foreground: #1a1a1a;
  --primary: #4ac6d6;
  --primary-hover: #3ab5c5;
  --muted-foreground: #6b7280;
  --radius: 0.625rem;
}

body {
  font-family: var(--font-sans);
  background-color: var(--background);
  color: var(--foreground);
}

h1, h2, h3, h4 {
  font-family: var(--font-heading);
  font-style: italic;
  font-weight: 500;
}
```

3. Update `tailwind.config.js` to extend with custom fonts:
```js
theme: {
  extend: {
    fontFamily: {
      sans: ['Karla', 'sans-serif'],
      heading: ['Petrona', 'serif'],
    },
    colors: {
      primary: '#4ac6d6',
    }
  }
}
```

### Acceptance Criteria
- [ ] Google Fonts load in browser (verify in Network tab)
- [ ] `h1` elements render in Petrona italic
- [ ] Body text renders in Karla
- [ ] `#f8f9fa` page background visible

---

## Phase B: Layout Component (Sidebar + Header)

**File to replace:** `frontend/src/components/Layout/Layout.tsx`

This is the most complex component. Build it carefully.

### Sidebar Specification

The sidebar has two states: **expanded** (w-72) and **collapsed** (w-20). Toggle via a chevron button at the bottom.

**Expanded sidebar structure (top to bottom):**
1. **Logo area** (h-20) — full logo image, or "integrate health" text fallback
2. **Navigation links** (flex-1, scrollable):
   - "home" — `<Home />` icon + label, routes to `/`
   - "my account" — `<User />` icon + label, routes to `/settings`
   - "patients" — `<Users />` icon + collapsible section
     - When expanded: shows inline patient search + patient list
     - Patient list items show: date (xs, gray-500), patient name, italic note text
     - Blue dot indicator (`w-2 h-2 bg-[#4ac6d6] rounded-full`) on left when sync is incomplete
3. **Bottom bar:**
   - "contact support" button: `<MessageCircle />` icon, expands text on hover (spring animation)
   - Collapse/expand toggle: `<ChevronLeft />` rotates 180° when collapsed

**Collapsed sidebar:**
- Icons only, no labels
- Support and toggle buttons remain

**Active state for nav items:**
```tsx
className={`... ${isActive ? 'bg-[#4ac6d6]/10 text-gray-900' : 'text-gray-700 hover:bg-gray-100'}`}
```

### Header Specification

Right-aligned flex row with these elements (right to left: profile, new session button, recording indicator, error indicator):

1. **Profile link** → `/settings`:
   - Provider name: `text-sm text-gray-900`
   - "welcome back": `text-xs italic text-gray-500`
   - Avatar image (or fallback icon div, 48×48, rounded-full)

2. **"start new session" button** (only visible when NOT on home `/` route):
   - 180×48px, rounded-xl, border-2 border-[#4ac6d6], bg-[#4ac6d6]/20
   - Shine sweep animation on hover (see below)
   - Opens "New Session" modal

3. **Recording indicator** (only visible when a recording is in progress):
   - 180×48px, bg-red-50, border-2 border-red-500, rounded-xl
   - `<Mic />` with pulsing scale animation
   - Text: "recording" in red-500
   - Blinking dot

4. **Error/connection indicator** (when backend error exists):
   - 240×48px, bg-orange-50, border-2 border-orange-500, rounded-xl
   - Shaking `<AlertCircle />` (wiggle animation)
   - Dismissable via `<X />` button

**Shine sweep animation for buttons:**
```tsx
<motion.div
  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent pointer-events-none"
  animate={isHovered ? { x: ['0%', '200%'] } : { x: '-100%' }}
  transition={{ duration: 0.5, ease: "easeInOut" }}
/>
```

### New Session Modal

Triggered by "start new session" button and the home page hero button:
- Overlay: `bg-black/50`
- Card: `bg-white rounded-2xl p-8 max-w-md`
- Title: "New Patient Session" (h2)
- Input: patient name (border-2 border-[#4ac6d6])
- Shows current date below input in italic gray
- Buttons: "cancel" (outlined) + "create session" (filled teal)
- On create: calls existing visit creation API → navigates to `/visits/{id}`

### Support Modal

Triggered by "contact support" sidebar button:
- Textarea with "how can we help?" placeholder
- "cancel" + "submit request" buttons
- On submit: shows confirmation modal ("Your request has been received.")

### Integration with Existing Auth

The Layout must use `useAuth()` from `store/authStore.ts`. If the user is unauthenticated, redirect to `/login`. **Do not change the auth store logic.**

### Acceptance Criteria
- [ ] Sidebar expands and collapses smoothly
- [ ] Active route highlights correctly for all 3 nav items
- [ ] Patient list in sidebar is searchable
- [ ] Blue dot appears on patients with incomplete sync
- [ ] Header shows recording indicator only when recording is active
- [ ] "start new session" button hidden on home route `/`
- [ ] New session modal creates a visit and navigates to visit detail
- [ ] All Figma asset references replaced with real files or CSS fallbacks

---

## Phase C: Login Page

**File to replace:** `frontend/src/pages/Login.tsx`

### Layout
- Full-screen centered layout (`min-h-screen flex items-center justify-center`)
- Background: gradient (`#f8f9fa` base, can use gradient-bg image as full-screen BG if available)
- Max-width card: `max-w-md w-full`

### Card Contents
1. Logo (centered, max-w-[240px]) — or text fallback
2. "welcome back" h1
3. "Sign in to access your portal" — italic, gray-500, centered
4. Email input (border-2 border-[#4ac6d6])
5. Password input with show/hide toggle (`<Eye />` / `<EyeOff />` icons in teal)
6. "forgot password?" link (teal, right-aligned)
7. "sign in" submit button (full-width, bg-[#4ac6d6])

### API Integration
Connect to existing `POST /auth/login` endpoint via `api/auth.ts`. Store JWT in the existing `authStore`. **Do not change the auth store logic.**

Error handling: display inline error message above submit button for invalid credentials.

### Acceptance Criteria
- [ ] Form submits to existing backend auth endpoint
- [ ] JWT stored and user redirected to `/` on success
- [ ] Error message shown for invalid credentials
- [ ] Password show/hide toggle works
- [ ] "forgot password?" triggers appropriate UX (alert acceptable for MVP)

---

## Phase D: Home Page (Dashboard)

**File to replace:** `frontend/src/pages/Dashboard.tsx`

This replaces the existing Dashboard and becomes the landing page at route `/`.

### Layout
```
<div className="w-full h-full pt-[5%]">
  <h1>welcome back</h1>
  <p className="italic text-gray-500">Here's your practice overview</p>
  
  {/* Hero CTA Button */}
  <motion.button ...>start a new session</motion.button>

  {/* Recent Activity */}
  <h2>Recent Activity</h2>
  <div className="bg-white border border-[#4ac6d6] rounded-2xl p-8 shadow-md">
    {recentVisits.map(visit => (
      <div key={visit.id} className="border-b border-gray-100 pb-6">
        <div className="text-xs text-gray-500">{formatted date/time}</div>
        <div>{patient_ref} — {chief_complaint}</div>
        <div className="italic text-gray-500">{transcription_status}</div>
      </div>
    ))}
  </div>
</div>
```

### Hero Button
- Full-width, h-150px, rounded-2xl, border-2 border-[#4ac6d6]
- Background: gradient image, or CSS gradient fallback
- Text: "start a new session" in white, text-3xl, drop-shadow
- Hover: scale 1.02 (spring), shine sweep animation
- Tap: scale 0.98
- onClick: opens New Session modal (same modal as Layout header button)

### Recent Activity Section
- Fetch from `GET /visits` API (limit 3, sorted by date desc)
- Show: visit date/time, patient_ref + chief_complaint, status
- While loading: show skeleton placeholders
- Empty state: italic gray text "No recent visits"

### Acceptance Criteria
- [ ] Hero button opens new session modal
- [ ] Recent visits fetched from real API and displayed
- [ ] Loading and empty states handled
- [ ] Page renders correctly as home route `/`

---

## Phase E: Visit Detail Page (Speak → Summarize → Sync Workflow)

**File to replace:** `frontend/src/pages/VisitDetail.tsx`

This is the core clinical workflow page. It replaces the existing VisitDetail and integrates the existing AudioRecorder and NoteEditor into a step-based UI.

### Route
`/visits/:visitId` (maps to existing backend `GET /visits/{visit_id}`)

### Page Header
```tsx
<div className="mb-8 flex items-start justify-between mt-12">
  <div>
    <h1 className="text-4xl">{patient_ref}</h1>
    <div className="flex items-center gap-3">
      {/* Editable visit title / chief complaint */}
      <EditableField value={chiefComplaint} onSave={...} italic gray />
      <span>•</span>
      {/* Editable date with calendar picker */}
      <CalendarField value={visitDate} onSave={...} />
      <span>•</span>
      {/* Editable time */}
      <EditableField value={visitTime} onSave={...} />
    </div>
  </div>
  <button className="text-gray-400 hover:text-red-500">
    <Trash2 size={20} />
  </button>
</div>
```

The editable fields update their values inline on blur/Enter. Changes persist via `PUT /visits/{visit_id}`.

Delete button calls `DELETE /visits/{visit_id}` and navigates back to `/`.

### Three-Step Progress Indicator

```
[1: speak] ——— [2: summarize] ——— [3: sync]
```

**Step circle states:**
- **Future:** white circle, gray border, gray number
- **Current:** teal gradient background, white number (or teal progress ring for sync step when partially complete)
- **Completed:** teal gradient background, white checkmark `<Check />`

**Sync step progress ring:** When sync step is active and 1–3 of 4 SOAP sections have been synced, show an SVG circular progress ring in teal around a gray circle background. The ring fills proportionally (1/4, 2/4, 3/4). When all 4 sections synced → full gradient checkmark.

Connector lines between steps: `w-24 h-0.5` — teal if step before is complete, gray otherwise.

### Step 1: Speak

This step wraps the existing `AudioRecorder` component.

```tsx
<div>
  {/* Transcript display area */}
  <div className="bg-white border border-[#4ac6d6] rounded-2xl p-6 mb-4 min-h-[120px] flex items-center justify-center">
    {isRecording ? (
      <span className="text-gray-600">Recording in progress...</span>
    ) : transcript ? (
      <p className="text-gray-700">{transcript}</p>
    ) : (
      <span className="text-gray-400 italic">Transcript will appear here</span>
    )}
  </div>

  {/* Record toggle button */}
  <button
    onClick={toggleRecording}
    className="relative w-full h-16 rounded-xl overflow-hidden hover:opacity-90"
    style={{ background: 'linear-gradient(135deg, #4ac6d6, #2a8fa0)' }}
  >
    <span className="text-white font-normal drop-shadow-md">
      {isRecording ? 'stop recording' : 'start recording'}
    </span>
  </button>
</div>
```

**Backend integration:**
- "start recording" → calls existing `useAudioRecorder` hook → starts MediaRecorder
- "stop recording" → stops recording, uploads blob to `POST /visits/{visitId}/audio`
- Polls `GET /visits/{visitId}/transcription/status` every 3 seconds until `status === 'completed'`
- When transcript ready → auto-advance to step 2 (summarize) OR let provider manually advance
- Show `<Loading />` while transcribing
- Show error state if transcription fails

### Step 2: Summarize

This step shows the SOAP note editor and patient summary.

**Trigger note generation:**
- When entering step 2 and transcript exists but note doesn't → auto-call `POST /visits/{visitId}/notes/generate`
- Show loading spinner in each SOAP section while generating
- On success → populate each section with generated content

**SOAP sections (S, O, A, P):**
```tsx
{['subjective', 'objective', 'assessment', 'plan'].map(section => (
  <div key={section} className="bg-white border border-[#4ac6d6] rounded-2xl p-6">
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-lg capitalize">{section}</h3>
      <div className="flex items-center gap-2">
        {copiedSection === section && (
          <span className="text-xs text-green-600">Copied!</span>
        )}
        <button
          onClick={() => handleSync(section)}
          className={`px-4 py-1.5 text-white text-sm rounded-lg transition-colors ${
            syncedSections[section]
              ? 'bg-green-500'
              : 'bg-[#4ac6d6] hover:bg-[#3ab5c5]'
          }`}
        >
          {syncedSections[section] ? <Check size={14} /> : 'sync'}
        </button>
      </div>
    </div>
    <textarea
      value={noteContent[section]}
      onChange={(e) => updateNoteSection(section, e.target.value)}
      className="w-full min-h-[80px] resize-y text-gray-700 focus:outline-none"
      placeholder={sectionPlaceholders[section]}
    />
  </div>
))}
```

**"Sync" button behavior — clipboard copy (no API call):**

This is the MVP workflow for getting notes into Practice Fusion: the provider clicks sync on each section, the text is copied to their clipboard, and they paste it manually into the EHR.

```tsx
const [copiedSection, setCopiedSection] = useState<string | null>(null);

const handleSync = async (section: keyof SyncStatus) => {
  const text = noteContent[section];
  if (text) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(section);
      setTimeout(() => setCopiedSection(null), 1500);
    } catch {
      // Fallback: silently fail, still mark as synced
      console.warn('Clipboard write failed for section:', section);
    }
  }
  setSyncedSections(prev => ({ ...prev, [section]: true }));
  // Advance to step 3 on first sync click
  if (currentStep < 2) setCurrentStep(2);
};
```

After clicking sync:
- Button turns green with a `<Check />` icon — **button remains clickable** so provider can re-copy
- A "Copied!" label appears inline next to the button and fades out after 1.5s
- Section is marked synced, which advances the step 3 progress ring

> **Note for future implementation:** When EHR write-back is available (Practice Fusion partnership), replace the clipboard copy in `handleSync` with an API call. The UI, step progression, and progress ring logic stay identical.

**Patient Summary section:**
```tsx
<div className="bg-white border border-[#4ac6d6] rounded-2xl p-6">
  <h3 className="text-lg mb-4">Patient Summary</h3>
  <textarea ... placeholder="Patient-friendly summary will appear here" />
  <div className="flex items-center gap-3 mt-4">
    <input type="email" placeholder="patient@email.com" className="flex-1 ..." />
    <button onClick={handlePrint}><Printer size={20} /></button>
    <button onClick={() => setShowSendConfirmation(true)}><Send size={20} /></button>
  </div>
</div>
```

**Send patient summary — visual confirmation only (no API call):**
- Clicking `<Send />` opens a confirmation modal: "Are you sure you want to send the patient summary to the patient?"
- The email address entered in the input is displayed in the modal for reference
- Confirming closes the modal and shows a brief success state — **no email is actually sent in this MVP**
- The print button calls `window.print()`

> **Note for future implementation:** Wire the send action to a backend email endpoint. The email address input, confirmation modal, and success state are already in place.

### Step 3: Sync

Visually identical to Step 2 (shows same SOAP sections + patient summary). The distinction is that this step is specifically for reviewing sync status of all sections.

**Sync progress:**
- Track which of the 4 SOAP sections have been synced
- Show the SVG circular progress ring on the step 3 circle indicator proportionally
- When all 4 sections synced → step 3 circle shows full gradient + checkmark

**Note:** The "sync" in the Figma design refers to syncing notes to the EHR (Practice Fusion). For MVP, this is a clipboard copy action — the provider copies each section and pastes into Practice Fusion manually. No API call is made when sync is clicked. The step 3 view is for final review of which sections have been copied.

### Acceptance Criteria
- [ ] Progress bar advances correctly through 3 steps
- [ ] Step circles show correct state (future/current/complete)
- [ ] Step 1: AudioRecorder works, transcript appears on completion
- [ ] Step 2: SOAP note auto-generated when transcript exists
- [ ] Step 2: Each SOAP section is editable in a textarea
- [ ] Step 2: Sync button copies section text to clipboard and shows green checkmark + "Copied!" feedback
- [ ] Step 2: Sync button remains clickable after syncing (provider may re-copy)
- [ ] Step 2: Patient summary send button shows confirmation modal (no email sent)
- [ ] Step 2: Print button triggers window.print()
- [ ] Step 3: Sync progress ring fills proportionally
- [ ] Step 3: All sections synced → full checkmark on step 3
- [ ] Patient name in header derived from `patient_ref`
- [ ] Visit date/title/time are inline-editable
- [ ] Delete button removes visit and navigates back to `/`

---

## Phase F: Patients List Page

**File to add:** `frontend/src/pages/PatientsList.tsx`

New page at route `/patients`.

```tsx
export function PatientsList() {
  // Fetch from GET /visits API
  // Group/display as patient records (patient_ref as name)
  
  return (
    <div className="w-full h-full">
      <div className="mb-8 mt-12">
        <h1>Patients</h1>
        <p className="italic text-gray-500">View all patient records</p>
      </div>

      {/* Search */}
      <div className="mb-8 max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input placeholder="find a patient" className="w-full pl-10 pr-4 py-3 border border-[#4ac6d6] rounded-xl ..." />
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredVisits.map(visit => (
          <Link to={`/visits/${visit.id}`} key={visit.id}
            className="bg-white border border-[#4ac6d6] rounded-2xl p-6 hover:shadow-lg transition-shadow">
            <div className="text-xs text-gray-500 mb-2">{formatDate(visit.visit_date)}</div>
            <div className="text-lg text-gray-900 mb-2">{visit.patient_ref}</div>
            <div className="text-sm italic text-gray-500">{visit.chief_complaint}</div>
          </Link>
        ))}
      </div>

      {filteredVisits.length === 0 && (
        <div className="text-center py-12 text-gray-500 italic">No patients found</div>
      )}
    </div>
  );
}
```

**Backend:** `GET /visits` (existing endpoint). Filter by search query client-side.

### Acceptance Criteria
- [ ] Lists all visits from API as patient cards
- [ ] Search filters by patient_ref or chief_complaint
- [ ] Cards link to `/visits/{id}`
- [ ] Empty state shown when no results

---

## Phase G: Settings Page

**File to update:** `frontend/src/pages/Settings.tsx` (or create if doesn't exist)

Mostly a UI update. Connect fields to actual logged-in user data from `/auth/me`.

```tsx
export function Settings() {
  const { user } = useAuth(); // from authStore

  return (
    <div className="w-full h-full">
      <h2 className="mb-6">Profile Information</h2>
      <div className="bg-white border border-[#4ac6d6] rounded-2xl p-8 shadow-md">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* First Name, Last Name inputs */}
          {/* Email input */}
          {/* Phone Number input with (xxx) xxx-xxxx formatter */}
        </div>
        <button className="mt-8 px-8 py-3 bg-[#4ac6d6] text-gray-900 rounded-xl hover:bg-[#3ab5c5]">
          save changes
        </button>
      </div>

      {/* Notification Preferences section */}
      <div className="mt-12">
        <h2 className="mb-6">Notification Preferences</h2>
        <div className="bg-white border border-[#4ac6d6] rounded-2xl p-8 shadow-md">
          {/* Toggle switches for: Email, Push, SMS, Marketing */}
        </div>
      </div>

      {/* Logout */}
      <button onClick={handleLogout} className="mt-12 flex items-center gap-2 text-red-500 hover:text-red-700">
        <LogOut size={16} />
        sign out
      </button>
    </div>
  );
}
```

### Acceptance Criteria
- [ ] Displays actual user info from `/auth/me`
- [ ] "Save changes" calls update endpoint or shows success message
- [ ] Notification toggles render with teal active state
- [ ] Sign out calls existing logout + redirects to `/login`

---

## Phase H: Common Components Update

Update these shared components to match the new design tokens. **Do not break their existing interfaces.**

### Button.tsx
```tsx
// Variants:
// primary: bg-[#4ac6d6] text-gray-900 hover:bg-[#3ab5c5] rounded-xl px-6 py-3
// outline: border-2 border-[#4ac6d6] text-gray-900 hover:bg-gray-50 rounded-xl px-6 py-3
// ghost: text-gray-700 hover:bg-gray-100 rounded-lg
// danger: text-red-500 hover:text-red-700
```

### Input.tsx
```tsx
// All inputs: border-2 border-[#4ac6d6] rounded-xl px-4 py-3 
// focus: outline-none ring-2 ring-[#4ac6d6]
// placeholder: italic text-gray-400
```

### Card.tsx
```tsx
// Default: bg-white border border-[#4ac6d6] rounded-2xl p-6 shadow-md
// Featured: bg-white border-2 border-[#4ac6d6] rounded-2xl p-8 shadow-md
```

---

## Phase I: Router & App.tsx Updates

**Files to update:** `frontend/src/App.tsx`, `frontend/src/main.tsx`

### New Routes (update `App.tsx`)
```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout/Layout';
import { ProtectedRoute } from './components/ProtectedRoute'; // create if doesn't exist
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import VisitDetail from './pages/VisitDetail';
import PatientsList from './pages/PatientsList';
import Settings from './pages/Settings';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="patients" element={<PatientsList />} />
          <Route path="visits/:visitId" element={<VisitDetail />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

> **Note:** Existing routes `/visits/:visitId` replaces the old `/visit/:visitId` route. Verify existing visit links in the codebase match this pattern.

### ProtectedRoute Component
Create `frontend/src/components/ProtectedRoute.tsx`:
```tsx
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}
```

### Acceptance Criteria
- [ ] `/login` → Login page (unauthenticated users always land here)
- [ ] `/` → Dashboard (authenticated)
- [ ] `/patients` → PatientsList (authenticated)
- [ ] `/visits/:visitId` → VisitDetail (authenticated)
- [ ] `/settings` → Settings (authenticated)
- [ ] Unknown routes → redirect to `/`
- [ ] Unauthenticated access to any protected route → redirect to `/login`

---

## Phase J: Types Update

**File to update:** `frontend/src/types/index.ts`

Add the following types:

```typescript
// Sync status for SOAP sections
export interface SyncStatus {
  subjective: boolean;
  objective: boolean;
  assessment: boolean;
  plan: boolean;
}

// Extended Visit type with sync UI state
export interface VisitWithSync extends Visit {
  syncStatus?: SyncStatus;
}
```

---

## Migration Notes for Existing Verified Features

The following existing features from Phases 1–5 must continue working unchanged. Claude Code must verify each after implementing the new UI.

| Feature | How to Verify |
|---------|--------------|
| User registration | `POST /auth/register` works from login page |
| User login / JWT | Login form → token stored → redirected to `/` |
| Protected routes | Visiting `/` while logged out → redirects to `/login` |
| Create visit | New session modal → API call → navigates to visit detail |
| List visits | Dashboard recent activity + PatientsList fetches `GET /visits` |
| Visit detail | `/visits/:id` loads from `GET /visits/{visit_id}` |
| Audio upload | Step 1 "stop recording" → `POST /visits/{visitId}/audio` |
| Transcription polling | Status polling from `GET /visits/{visitId}/transcription/status` |
| Transcript display | Appears in step 1 area when `transcription_status === 'completed'` |

---

## Do Not Change

The following files must not be modified:

- `backend/` — entire directory
- `docker-compose.yml`
- `.env` / `.env.example`
- `frontend/src/api/` — all API client files (`client.ts`, `auth.ts`, `visits.ts`, `notes.ts`)
- `frontend/src/store/authStore.ts`
- `frontend/src/store/visitStore.ts`
- `frontend/src/hooks/useAudioRecorder.ts`

---

## Implementation Order

Implement phases in this exact sequence. Complete and verify acceptance criteria before moving to the next phase.

```
A → B → C → I → D → E → F → G → H → J
Global   Layout  Login  Router  Home  Visit  Patients  Settings  Common  Types
Styles   
```

**Why this order:**
- Phase A (styles) must come first so all components have fonts + CSS variables
- Phase B (Layout) must come before page components since it's the shell
- Phase C (Login) and Phase I (Router) must work together so auth flow is testable
- Phases D–G (pages) can then be implemented with a working shell
- Phase H (common components) and Phase J (types) are cleanup/polish

---

## Key Differences from Current Implementation

| Current Implementation | New Design |
|------------------------|------------|
| Single-step visit view | 3-step workflow: speak → summarize → sync |
| Separate NoteEditor page | NoteEditor integrated into VisitDetail step 2 |
| No patient list page | New `/patients` grid page |
| Generic Bootstrap/Tailwind styling | Custom Petrona/Karla typography + teal `#4ac6d6` design system |
| Static sidebar (no collapse) | Collapsible sidebar with patient search |
| No recording/error indicators in header | Live recording indicator + dismissable error badges |
| No support contact flow | "contact support" modal in sidebar |
| Dashboard shows action cards | Dashboard shows "start session" hero + recent activity |

---

*For Claude Code: Follow phases sequentially. Complete all acceptance criteria before moving to the next phase. If an existing file path is referenced and doesn't match the actual project structure, check the current file tree before assuming it needs to be created.*

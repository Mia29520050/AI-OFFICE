---
name: motion
description: Motion design principles, Disney's 12 principles for UI, timing curves, and spring physics for AI-Office.
---
# Motion Design Skill

Universal motion design principles adapted from `LottieFiles/motion-design-skill` for AI-Office desktop UI, Manga Studio transitions, and Live2D interactions.

## 1. Core Philosophy (Disney Principles Adapted for Digital UI)
- **Anticipation**: Small preparatory cues before major spatial shifts (e.g., slight scale-down on button press before modal opening).
- **Follow-Through & Overlap**: Elements don't stop abruptly together; secondary actions (badges, text) trail slightly behind main containers (stagger 40–80ms).
- **Staging**: Direct user attention to one primary focus; avoid simultaneous competing high-velocity animations.
- **Slow In & Slow Out (Easing)**: Never use linear motion for spatial translation. Always use cubic-bezier deceleration (`cubic-bezier(0.16, 1, 0.3, 1)`) or spring dynamics.

## 2. Timing Reference Table
| Interaction Type | Recommended Duration | Easing Curve |
| :--- | :--- | :--- |
| **Micro-interactions** (hover, toggle, active) | 120ms – 180ms | `ease-out` / `cubic-bezier(0.2, 0, 0, 1)` |
| **Modal / Omnibar Expansion** | 220ms – 300ms | Spring overshoot or `cubic-bezier(0.16, 1, 0.3, 1)` |
| **Page / Panel Cross-Transitions** | 300ms – 400ms | Decelerate in, stagger secondary elements |
| **Toast & Badges Entrance** | 200ms – 250ms | Spring pop (`scale(0.95) -> scale(1.0)`) |

## 3. 8-Step Motion Checklist
1. Is spatial movement using non-linear easing? (Reject `transition: all linear`).
2. Are durations proportional to distance traveled?
3. Do exiting elements animate faster than entering elements (approx. 20% faster)?
4. Is multi-element entrance choreographed with subtle staggering (30–60ms per child)?
5. Does the animation honor user accessibility preferences (`@media (prefers-reduced-motion)`)?
6. Is GPU composition leveraged via `transform` and `opacity` (avoid animating `top`, `left`, `width`, `height` directly)?
7. Does Live2D breathing / blinking follow natural sinusoidal easing?
8. Are screentone and panel zoom in Manga Studio locked to 60fps frame budgets?

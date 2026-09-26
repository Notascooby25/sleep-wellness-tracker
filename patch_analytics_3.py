with open('frontend-web/src/routes/analytics/+page.svelte', 'r') as f:
    content = f.read()

old_logic = """  $: influenceMoodScores = (() => {
    const actMap = new Map<string, { with: number[]; without: number[] }>();
    
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const score = Number(e.mood_score);
      for (const aid of activities) {
        const name = aid.name;
        if (!actMap.has(name)) actMap.set(name, { with: [], without: [] });
        
        if ((e.activity_ids || []).includes(aid.id)) {
          actMap.get(name)!.with.push(score);
        }
      }
    }
    
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const score = Number(e.mood_score);
      for (const aid of activities) {
        const name = aid.name;
        if (!(e.activity_ids || []).includes(aid.id)) {
          actMap.get(name)!.without.push(score);
        }
      }
    }"""

new_logic = """  $: influenceMoodScores = (() => {
    const actMap = new Map<string, { with: number[]; without: number[] }>();
    
    // Pass 1: Build the 'with' keys
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const score = Number(e.mood_score);
      const eActivityIds = e.activity_ids || [];
      const eDetailsMap = new Map((e.activity_details || []).map(d => [d.activity_id, d]));
      
      for (const aid of activities) {
        if (eActivityIds.includes(aid.id)) {
          const det = eDetailsMap.get(aid.id);
          let name = aid.name;
          if (det?.quantity_numeric != null) {
            name = `${aid.name} (Qty: ${det.quantity_numeric})`;
          } else if (det?.severity != null) {
            name = `${aid.name} (Sev: ${det.severity})`;
          }
          if (!actMap.has(name)) actMap.set(name, { with: [], without: [] });
          actMap.get(name)!.with.push(score);
        } else {
          // ensure base activity exists in actMap even if never logged (original behavior)
          if (!actMap.has(aid.name)) actMap.set(aid.name, { with: [], without: [] });
        }
      }
    }
    
    // Pass 2: Populate 'without' for all discovered variants
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const score = Number(e.mood_score);
      const eActivityIds = e.activity_ids || [];
      const eDetailsMap = new Map((e.activity_details || []).map(d => [d.activity_id, d]));
      
      for (const key of actMap.keys()) {
        // Did the user log THIS exact variant today?
        // A simple way to check is to re-compute today's variant names
        let didLogThisExactVariant = false;
        for (const aid of activities) {
          if (eActivityIds.includes(aid.id)) {
            const det = eDetailsMap.get(aid.id);
            let name = aid.name;
            if (det?.quantity_numeric != null) {
              name = `${aid.name} (Qty: ${det.quantity_numeric})`;
            } else if (det?.severity != null) {
              name = `${aid.name} (Sev: ${det.severity})`;
            }
            if (name === key) {
              didLogThisExactVariant = true;
              break;
            }
          }
        }
        
        if (!didLogThisExactVariant) {
          actMap.get(key)!.without.push(score);
        }
      }
    }"""
content = content.replace(old_logic, new_logic)

with open('frontend-web/src/routes/analytics/+page.svelte', 'w') as f:
    f.write(content)

const fs = require('fs');
const file = 'frontend-web/src/routes/acupuncture-report/+page.svelte';
let content = fs.readFileSync(file, 'utf8');

content = content.replace(
  `  const addExclude = () => {
    if (excludeInput && !excludeActivities.includes(excludeInput)) {
      excludeActivities = [...excludeActivities, excludeInput];
      excludeInput = '';
      loadSummary();
    }
  };`,
  `  const addExclude = () => {
    if (excludeInput && !excludeActivities.includes(excludeInput)) {
      excludeActivities = [...excludeActivities, excludeInput];
      localStorage.setItem('headache_exclude_activities', JSON.stringify(excludeActivities));
      excludeInput = '';
      loadSummary();
    }
  };`
);

content = content.replace(
  `  const removeExclude = (act: string) => {
    excludeActivities = excludeActivities.filter(a => a !== act);
    loadSummary();
  };`,
  `  const removeExclude = (act: string) => {
    excludeActivities = excludeActivities.filter(a => a !== act);
    localStorage.setItem('headache_exclude_activities', JSON.stringify(excludeActivities));
    loadSummary();
  };`
);

content = content.replace(
  `  onMount(() => {
    loadInitial();
  });`,
  `  onMount(() => {
    const saved = localStorage.getItem('headache_exclude_activities');
    if (saved) {
      try {
        excludeActivities = JSON.parse(saved);
      } catch (e) {}
    }
    loadInitial();
  });`
);

fs.writeFileSync(file, content);

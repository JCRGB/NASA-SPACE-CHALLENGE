import dataUrl from '../../../data/processed/suitability.json?url';

export default Object.freeze({
    key: 'suitability',
    dataUrl,
    title: 'LANDING SUITABILITY',
    unit: 'score · 0–100',
    source: 'Derived from NASA illumination and LDEC terrain',
    min: 0,
    max: 100,
    stops: ['#f02d38', '#ffe34d', '#19d477'],
    labels: ['0 hazardous', '100 optimal'],
    value: point => point.value,
});

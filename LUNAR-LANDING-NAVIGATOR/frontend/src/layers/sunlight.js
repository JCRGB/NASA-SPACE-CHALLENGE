import dataUrl from '../../../data/processed/sunlight.json?url';

export default Object.freeze({
    key: 'sunlight',
    dataUrl,
    title: 'LUNAR ILLUMINATION',
    unit: '% sunlight',
    source: 'NASA LOLA AVGVISIB 65S · 240 m',
    min: 0,
    max: 100,
    stops: ['#271044', '#2474e8', '#ffe52e'],
    labels: ['0%', '100%'],
    value: point => point.illumination_pct ?? point.value,
});

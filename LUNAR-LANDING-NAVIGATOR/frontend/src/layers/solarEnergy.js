import dataUrl from '../../../data/processed/solar_energy.json?url';

export default Object.freeze({
    key: 'solar',
    dataUrl,
    title: 'DAILY SOLAR ENERGY',
    unit: 'kWh/m²/day',
    source: 'Derived from NASA illumination · 20% panel efficiency',
    min: 0,
    max: 6.5328,
    stops: ['#123bba', '#04d6e8', '#ffd338', '#f13a30'],
    labels: ['0', '6.53'],
    value: point => point.value,
});

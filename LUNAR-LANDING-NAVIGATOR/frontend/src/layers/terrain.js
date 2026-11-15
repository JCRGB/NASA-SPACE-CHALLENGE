const dataUrl = '/data/processed/terrain.json';

export default Object.freeze({
    key: 'terrain',
    dataUrl,
    title: 'TERRAIN SLOPE',
    unit: 'degrees',
    source: 'LDEC 60S 240 m DEM · calculated slope',
    min: 0,
    max: 30,
    stops: ['#12ca76', '#ffa52f', '#ec3437'],
    labels: ['0° flat', '30° steep'],
    value: point => point.slope_degrees ?? point.value,
});

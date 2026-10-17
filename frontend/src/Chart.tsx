export function Chart({ values, color = '#b8f465' }: {
    values: number[];
    color?: string;
}) {
    const series = values.length > 1 ? values : [values[0] ?? 0, values[0] ?? 0];
    const min = Math.min(...series), range = Math.max(...series) - min || 1;
    const points = series.map((v, i) => `${i / (series.length - 1) * 1000},${155 - (v - min) / range * 125}`).join(' ');
    return <svg viewBox="0 0 1000 180" preserveAspectRatio="none" role="img" aria-label="Serie temporal">
    <defs>
    <linearGradient id={'fill' + color.slice(1)} x1="0" y1="0" x2="0" y2="1">
    <stop stopColor={color} stopOpacity=".18"/>
    <stop offset="1" stopColor={color} stopOpacity="0"/>
    </linearGradient>
    </defs>{[30, 75, 120, 165].map(y => <line key={y} x1="0" x2="1000" y1={y} y2={y} stroke="#26312d"/>)}<polygon points={`0,180 ${points} 1000,180`} fill={`url(#fill${color.slice(1)})`}/>
    <polyline points={points} stroke={color} strokeWidth="2.5" fill="none" vectorEffect="non-scaling-stroke"/>
    </svg>;
}

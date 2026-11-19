export default function Select({ id, label, value, onChange, options, allLabel = "All" }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="overline">{label}</span>
      <select data-testid={id} className="qselect" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        {allLabel && <option value="">{allLabel}</option>}
        {options.map((o) => (
          <option key={String(o.value ?? o)} value={o.value ?? o}>{o.label ?? o}</option>
        ))}
      </select>
    </label>
  );
}

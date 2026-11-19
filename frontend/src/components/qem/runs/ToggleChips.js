export default function ToggleChips({ id, label, options, value, onChange, locked = [] }) {
  const toggle = (v) => {
    if (locked.includes(v)) return;
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  };
  return (
    <div className="flex flex-col gap-2">
      <span className="overline">{label}</span>
      <div className="flex flex-wrap gap-1.5" data-testid={id}>
        {options.map((o) => {
          const v = o.value ?? o;
          return (
            <button type="button" key={String(v)} data-testid={`${id}-${String(v).replaceAll(".", "_")}`} data-active={value.includes(v)}
              disabled={locked.includes(v)} className="togglechip" onClick={() => toggle(v)} title={o.title}>
              {o.label ?? o}
            </button>
          );
        })}
      </div>
    </div>
  );
}

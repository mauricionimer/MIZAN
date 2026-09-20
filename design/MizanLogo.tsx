// Mizan — logo (símbolo de gráfico ascendente) + wordmark.
// Símbolo: três barras inclinadas subindo, em degradê de azul.
// Uso:
//   <MizanMark size={32} />                    // só o símbolo
//   <MizanLogo size={28} />                    // símbolo + "Mizan"
//   <MizanLogo size={28} wordClassName="..." /> // estilize o texto por fora

import * as React from "react";

export function MizanMark({
  size = 30,
  className,
  title = "Mizan",
}: {
  size?: number;
  className?: string;
  title?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 30 30"
      className={className}
      role="img"
      aria-label={title}
    >
      <polygon points="6.5,15 11.5,15 9,27 4,27" fill="#b8c0ee" />
      <polygon points="13.5,9 18.5,9 16,27 11,27" fill="#8f9be9" />
      <polygon points="20.5,3 25.5,3 23,27 18,27" fill="#5966d9" />
    </svg>
  );
}

export function MizanLogo({
  size = 28,
  gap = 10,
  className,
  wordClassName,
}: {
  size?: number;      // altura do símbolo em px
  gap?: number;
  className?: string;
  wordClassName?: string;
}) {
  return (
    <span
      className={className}
      style={{ display: "inline-flex", alignItems: "center", gap }}
    >
      <MizanMark size={size} />
      <span
        className={wordClassName}
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 700,
          fontSize: size * 1.05,
          letterSpacing: "-0.03em",
          lineHeight: 1,
          color: "currentColor",
        }}
      >
        Mizan
      </span>
    </span>
  );
}

export default MizanLogo;

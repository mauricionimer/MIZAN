import React from "react"

// Campo de entrada do login em estilo glass. Adaptado do gaming-login (21st.dev):
// ícone à esquerda, fundo translúcido e borda fina. As cores vêm das variáveis
// --glass-* do .login-card (index.css), para valer nos temas claro e escuro.

interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon: React.ReactNode
  /** Elemento à direita do campo (ex.: botão de mostrar a senha). */
  trailing?: React.ReactNode
}

export function FormInput({ icon, trailing, className = "", ...rest }: FormInputProps) {
  return (
    <div className="relative">
      <div className="glass-input-icon absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true">
        {icon}
      </div>
      <input
        {...rest}
        className={`glass-input w-full pl-10 ${trailing ? "pr-11" : "pr-3"} py-2.5 ${className}`}
      />
      {trailing}
    </div>
  )
}

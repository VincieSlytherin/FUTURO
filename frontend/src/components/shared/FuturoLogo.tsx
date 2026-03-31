import Image from "next/image";

interface FuturoLogoProps {
  size: number;
  className?: string;
  alt?: string;
  priority?: boolean;
}

export default function FuturoLogo({
  size,
  className = "",
  alt = "Futuro logo",
  priority = false,
}: FuturoLogoProps) {
  return (
    <Image
      src="/futuro.png"
      alt={alt}
      width={size}
      height={size}
      priority={priority}
      className={className}
    />
  );
}

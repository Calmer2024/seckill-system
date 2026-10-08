import { ArrowLeft, ArrowRight, Upload, Zap, ChefHat, MessagesSquare, Check, ChevronRight, Monitor, Package, PackageOpen, Globe, House, Link, Search, Music, Image, ShieldCheck, ShoppingCart, Sparkles, Grid2X2, Star, Tag, Award, UserRound, UserCheck, UserPlus, Gem } from 'lucide-react';

const icons = {
  'gem': Gem,
  'user-round': UserRound,
  'upload': Upload,
  'search': Search,
  'shopping-cart': ShoppingCart,
  'twitter': MessagesSquare,
  'facebook': Globe,
  'linkedin': Link,
  'instagram': Image,
  'check': Check,
  'chevron-right': ChevronRight,
  'grid-2x2': Grid2X2,
  'house': House,
  'music': Music,
  'monitor': Monitor,
  'chef-hat': ChefHat,
  'sparkles': Sparkles,
  'award': Award,
  'tag': Tag,
  'shield-check': ShieldCheck,
  'zap': Zap,
  'package-open': PackageOpen,
  'user-check': UserCheck,
  'user-plus': UserPlus,
  'arrow-left': ArrowLeft,
  'arrow-right': ArrowRight,
  'star': Star,
  'package': Package,
};

// Official Lucide geometry is bundled locally, alongside the observability sprite.
export function Icon({ icon, ...props }) {
  const Component = icons[icon];
  if (!Component) throw new Error(`Unknown Lucide icon: ${icon}`);
  return <Component aria-hidden="true" focusable="false" {...props} />;
}

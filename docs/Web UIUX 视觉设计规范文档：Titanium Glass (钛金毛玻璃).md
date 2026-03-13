# Web UI/UX 视觉设计规范文档：Titanium Glass (钛金毛玻璃)

## 一、 核心设计理念 (Core Philosophy)

本设计系统摒弃了过度的赛博朋克重金属感，转向**“克制、通透、呼吸感”**的现代极简主义。设计服务于内容本身，通过大面积留白、细腻的光影和真实的物理材质反馈，降低用户的认知负担，营造高端的数字商店体验。

## 二、 色彩系统 (Color Palette)

色彩体系从暗黑模式转变为明亮、清透的环境色。依赖色彩的微妙变化来划分层级，而非生硬的线条。

- **背景基色 (Base Background):** `Apple Gray` (#F5F5F7)。一种极其轻微的暖灰色，比纯白更护眼，也是承载高亮卡片的最佳底色。
- **卡片材质 (Card Material):** `Translucent White` (rgba(255, 255, 255, 0.65))。配合背景模糊使用，形成核心的毛玻璃面板。
- **主文本色 (Primary Text):** `Deep Obsidian` (#1D1D1F)。用于主标题和核心正文，提供极高的对比度和现代感。
- **次要文本 (Secondary Text):** `Slate Gray` (#86868B)。用于副标题、商品描述和次要信息。
- **强调/行动色 (Accent/Action):** `System Blue` (#0071E3) 用于常规可交互链接，`Confirm Green` (#10B981) 用于成功状态反馈（如购买成功）。

## 三、 字体排印 (Typography)

极其强调字体大小的对比度（Typography Scale）和字重（Font Weight）的搭配，利用字体排版本身构建视觉焦点。

- **展示级标题 (Display):** 优先采用 `SF Pro Display` 或 `Inter`。特征为**大字号、粗体 (Bold/Semibold)、紧凑字距 (tracking-tight)**。用于页面最顶部的宏大叙事（如：“选购最新产品。”）。
- **正文与UI (Body):** 优先采用 `SF Pro Text` 或 `Inter`。注重可读性，常规字重，适当的行高。
- **微排版 (Micro-typography):** 标签、状态说明采用全大写 (UPPERCASE)、极小字号 (text-xs) 和宽字距 (tracking-widest)，以此提升设计的精致感。

## 四、 材质与空间维度 (Materials & Spatial Depth)

这是本套规范的“灵魂”，通过 CSS 特效模拟真实的物理光学和材质。

- **分层透明 (Glassmorphism):** * 所有承载内容的卡片或顶栏，均采用高斯模糊 (`backdrop-blur-2xl` 或更高) 和半透明白色背景。
  - **关键细节：** 必须配有极细且带有透明度的白色边框 (`border-white/60`)，用于勾勒玻璃的边缘高光。
- **钛金属噪点 (Titanium Noise):** * 在全局背景最上层，覆盖一层极其细腻（极低透明度，约 0.02）、混合模式为正片叠底 (`mix-blend-mode: multiply`) 的噪点纹理。这能消除纯色背景的廉价感，带来类似铝合金或纸张的微观质感。
- **环境光底座 (Ambient Gradient):** * 背景并非纯色，而是在屏幕顶部中央有一个向外扩散的极浅白色径向渐变 (`radial-gradient`)，模拟顶灯打在展台上的聚光效果。
- **苹果式弥散阴影 (Diffuse Shadows):** * 彻底放弃生硬的小阴影。使用扩散范围极大、颜色极浅的阴影（如 `0 4px 24px rgba(0, 0, 0, 0.04)`）。悬停时，阴影范围进一步扩大，模拟卡片“浮起”的物理现象。

## 五、 布局与栅格 (Layout & Grid)

- **极简留白 (Breathable Whitespace):** 页面模块之间、标题与内容之间保持奢侈的留白（如 `py-24`, `mb-16`）。不使用任何实线分割线，完全依靠空间间距来划分区域。
- **瀑布流排列 (Masonry/Columns):** 在展示商品列表时，利用 CSS `columns` 属性实现错落有致的瀑布流。打破传统网格的死板，完美适应不同长宽比的商品卡片。
- **超级大圆角 (Hyper Rounded Corners):** 所有的卡片、按钮和图片容器，均采用超大圆角（如 `rounded-[2rem]` 或完全圆角的 `rounded-full` 按钮），以消除尖锐感，增加亲和力。

## 六、 交互与动效 (Interaction & Motion)

- **流体悬停 (Fluid Hover):** 鼠标悬停在商品卡片上时，卡片产生轻微的 Y 轴上浮（`y: -4`）和极小幅度的放大（`scale: 1.01`）。
- **弹簧物理 (Spring Animation):** 动画不使用线性的生硬过渡，而是借助 Framer Motion 使用带有阻尼的物理弹簧效果 (`type: "spring", stiffness: 300, damping: 20`)，让 UI 感觉是“有质量”的物体。
- **按钮状态反馈:** 点击购买按钮时，按钮有明显的下压反馈 (`whileTap={{ scale: 0.95 }}`)，并在成功后伴随平滑的颜色过渡和文字切换，拒绝突兀的弹窗提示。
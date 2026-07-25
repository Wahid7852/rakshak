#include <rakshak/widgets/ToastNotification.h>

#include <QtWidgets/QLabel>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QGraphicsOpacityEffect>
#include <QtWidgets/QApplication>
#include <QtGui/QScreen>
#include <QtGui/QPainter>
#include <QtGui/QPainterPath>
#include <QtCore/QTimer>
#include <QtCore/QPropertyAnimation>

using namespace rakshak::widgets;

namespace {
// Ledger palette - deliberately not Tailwind's #22C55E/#EF4444/#FBBF24.
constexpr auto kToastBg = "#1B1812";
constexpr auto kToastText = "#F4F1EA";
}

ToastNotification::ToastNotification(QWidget* parent)
    : QWidget(parent)
    , m_dotLabel(new QLabel(this))
    , m_messageLabel(new QLabel(this))
    , m_dismissTimer(new QTimer(this)) {
    setAttribute(Qt::WA_TranslucentBackground);
    setWindowFlags(Qt::FramelessWindowHint | Qt::Tool
                   | Qt::WindowStaysOnTopHint | Qt::NoDropShadowWindowHint);
    setAttribute(Qt::WA_ShowWithoutActivating);

    auto* layout = new QHBoxLayout(this);
    layout->setContentsMargins(16, 12, 18, 12);
    layout->setSpacing(10);

    m_dotLabel->setFixedSize(8, 8);
    m_messageLabel->setStyleSheet(QStringLiteral("color:%1; font-size:13px;").arg(kToastText));
    m_messageLabel->setWordWrap(false);

    layout->addWidget(m_dotLabel, 0, Qt::AlignVCenter);
    layout->addWidget(m_messageLabel, 0, Qt::AlignVCenter);

    auto* opacityEffect = new QGraphicsOpacityEffect(this);
    setGraphicsEffect(opacityEffect);
    m_fadeAnim = new QPropertyAnimation(opacityEffect, "opacity", this);

    m_dismissTimer->setSingleShot(true);
    connect(m_dismissTimer, &QTimer::timeout, this, &ToastNotification::onDismissTimeout);
    connect(m_fadeAnim, &QPropertyAnimation::finished, this, &ToastNotification::onFadeOutFinished);

    hide();
}

void ToastNotification::showToast(const QString& message, ToastType type, int durationMs) {
    m_queue.enqueue({message, type, durationMs});
    if (!m_isShowing) displayNext();
}

void ToastNotification::displayNext() {
    if (m_queue.isEmpty()) {
        m_isShowing = false;
        return;
    }

    m_isShowing = true;
    const QueuedToast toast = m_queue.dequeue();
    m_currentType = toast.type;
    m_messageLabel->setText(toast.message);

    adjustSize();
    setFixedSize(sizeHint());
    positionAtParentBottomRight();

    auto* opacityEffect = qobject_cast<QGraphicsOpacityEffect*>(graphicsEffect());
    opacityEffect->setOpacity(0.0);
    show();
    raise();

    m_fadeAnim->stop();
    m_fadeAnim->setDuration(180);
    m_fadeAnim->setStartValue(0.0);
    m_fadeAnim->setEndValue(1.0);
    m_fadeAnim->start();

    m_dismissTimer->start(toast.durationMs);
}

void ToastNotification::onDismissTimeout() {
    auto* opacityEffect = qobject_cast<QGraphicsOpacityEffect*>(graphicsEffect());
    m_fadeAnim->stop();
    m_fadeAnim->setDuration(220);
    m_fadeAnim->setStartValue(opacityEffect->opacity());
    m_fadeAnim->setEndValue(0.0);
    m_fadeAnim->start();
}

void ToastNotification::onFadeOutFinished() {
    auto* opacityEffect = qobject_cast<QGraphicsOpacityEffect*>(graphicsEffect());
    if (opacityEffect->opacity() > 0.01) return; // that was the fade-IN finishing

    hide();
    displayNext();
}

void ToastNotification::positionAtParentBottomRight() {
    if (QWidget* p = parentWidget()) {
        const QPoint bottomRight = p->mapToGlobal(
            QPoint(p->width() - width() - 24, p->height() - height() - 24));
        move(bottomRight);
    } else if (QScreen* screen = QApplication::primaryScreen()) {
        const QRect geo = screen->availableGeometry();
        move(geo.right() - width() - 24, geo.bottom() - height() - 24);
    }
}

QColor ToastNotification::colorForType(ToastType type) const {
    switch (type) {
        case ToastType::Success: return QColor("#5B7052"); // muted sage, not Tailwind green
        case ToastType::Warning: return QColor("#A8791F"); // ochre
        case ToastType::Danger:  return QColor("#7A1E1E"); // oxblood
        case ToastType::Info:
        default:                 return QColor("#6B6252"); // muted ink
    }
}

void ToastNotification::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    QPainterPath path;
    path.addRoundedRect(rect(), 4, 4); // hairline-square, not the generic rounded-card look
    painter.fillPath(path, QColor(kToastBg));

    QPen borderPen(colorForType(m_currentType));
    borderPen.setWidth(1);
    painter.setPen(borderPen);
    painter.drawPath(path);

    painter.setPen(Qt::NoPen);
    painter.setBrush(colorForType(m_currentType));
    painter.drawEllipse(m_dotLabel->geometry());
}

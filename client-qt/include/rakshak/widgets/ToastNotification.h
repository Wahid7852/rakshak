#pragma once

#include <QtWidgets/QWidget>
#include <QtCore/QQueue>
#include <QtCore/QString>
#include <QtGui/QColor>

class QLabel;
class QTimer;
class QPropertyAnimation;

namespace rakshak::widgets {

// A frameless, auto-dismissing toast anchored to its parent's bottom-right
// corner. Toasts queue rather than stack - one shows at a time.
class ToastNotification : public QWidget {
    Q_OBJECT
public:
    enum class ToastType { Info, Success, Warning, Danger };

    explicit ToastNotification(QWidget* parent = nullptr);

    void showToast(const QString& message, ToastType type = ToastType::Info, int durationMs = 3000);

protected:
    void paintEvent(QPaintEvent* event) override;

private slots:
    void onDismissTimeout();
    void onFadeOutFinished();

private:
    struct QueuedToast {
        QString message;
        ToastType type;
        int durationMs;
    };

    void displayNext();
    void positionAtParentBottomRight();
    QColor colorForType(ToastType type) const;

    QLabel* m_dotLabel;
    QLabel* m_messageLabel;
    QTimer* m_dismissTimer;
    QPropertyAnimation* m_fadeAnim;
    QQueue<QueuedToast> m_queue;
    ToastType m_currentType = ToastType::Info;
    bool m_isShowing = false;
};

} // namespace rakshak::widgets

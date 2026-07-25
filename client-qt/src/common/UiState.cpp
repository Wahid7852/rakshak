#include <rakshak/common/UiState.h>
#include <QtCore/QSettings>

namespace rakshak::common {

void saveUiState(const QString& key, const QByteArray& state) {
    QSettings s(QStringLiteral("RakshakOrg"), QStringLiteral("QuantumMLHunter"));
    s.setValue(QStringLiteral("uistate/%1").arg(key), state);
}

QByteArray loadUiState(const QString& key) {
    QSettings s(QStringLiteral("RakshakOrg"), QStringLiteral("QuantumMLHunter"));
    return s.value(QStringLiteral("uistate/%1").arg(key)).toByteArray();
}

} // namespace rakshak::common

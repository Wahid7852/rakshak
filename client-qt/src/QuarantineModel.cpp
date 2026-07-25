#include "rakshak/models/QuarantineModel.h"
#include <QtCore/QDateTime>

QuarantineModel::QuarantineModel(QObject* parent) : QAbstractTableModel(parent) {}

int QuarantineModel::rowCount(const QModelIndex&) const { return m_rows.size(); }
int QuarantineModel::columnCount(const QModelIndex&) const { return 4; }

QVariant QuarantineModel::data(const QModelIndex& idx, int role) const {
    if (!idx.isValid() || idx.row() < 0 || idx.row() >= m_rows.size()) return {};
    const auto& r = m_rows[idx.row()];
    if (role == Qt::DisplayRole) {
        switch (idx.column()) {
        case 0: return r.time;
        case 1: return r.filePath;
        case 2: return r.reason;
        case 3: return r.sha256;
        }
    }
    return {};
}

QVariant QuarantineModel::headerData(int section, Qt::Orientation o, int role) const {
    if (o == Qt::Horizontal && role == Qt::DisplayRole) {
        switch (section) {
        case 0: return "Quarantined";
        case 1: return "Original path";
        case 2: return "Reason";
        case 3: return "SHA-256";
        }
    }
    return {};
}

void QuarantineModel::setRows(QVector<QuarantineRow> rows) {
    beginResetModel();
    m_rows = std::move(rows);
    endResetModel();
}

bool QuarantineModel::removeRowById(const QString& quarantineId) {
    for (int i = 0; i < m_rows.size(); ++i) {
        if (m_rows[i].quarantineId == quarantineId) {
            beginRemoveRows(QModelIndex(), i, i);
            m_rows.removeAt(i);
            endRemoveRows();
            return true;
        }
    }
    return false;
}

QString QuarantineModel::quarantineIdAt(int row) const {
    if (row < 0 || row >= m_rows.size()) return {};
    return m_rows[row].quarantineId;
}

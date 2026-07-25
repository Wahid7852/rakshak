#pragma once
#include <QtCore/QAbstractTableModel>
#include <QtCore/QVector>
#include <QtCore/QString>

// Mirrors rakshak::backend::QuarantineEntryDto - one row per file the real
// backend has quarantined.
struct QuarantineRow {
    QString quarantineId;
    QString time;
    QString filePath;
    QString reason;
    QString sha256;
};

class QuarantineModel : public QAbstractTableModel {
    Q_OBJECT
public:
    explicit QuarantineModel(QObject* parent = nullptr);
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    int columnCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role) const override;
    QVariant headerData(int section, Qt::Orientation orientation, int role) const override;

    // Replaces the whole table - called after a fresh ApiClient::listQuarantine().
    void setRows(QVector<QuarantineRow> rows);
    // Removes the row for a given quarantine id after a successful
    // restore/delete, without a full refetch.
    bool removeRowById(const QString& quarantineId);
    QString quarantineIdAt(int row) const;

private:
    QVector<QuarantineRow> m_rows;
};

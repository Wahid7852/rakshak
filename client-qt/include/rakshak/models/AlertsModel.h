#pragma once
#include <QtCore/QAbstractTableModel>
#include <QtCore/QVector>
#include <QtCore/QString>
#include <QtCore/QVariant>
#include <QtCore/QModelIndex>

struct AlertRow {
    QString timestamp;
    QString severity;
    QString srcIp;
    QString dstIp;
    QString ruleId;
    double score;
    QString json;
};

class AlertsModel : public QAbstractTableModel {
    Q_OBJECT
public:
    explicit AlertsModel(QObject* parent = nullptr);
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    int columnCount(const QModelIndex& parent = QModelIndex()) const override;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;
    QVariant headerData(int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;

    void addAlert(const AlertRow& row);
    const AlertRow& at(int row) const { return m_rows[row]; }
private:
    QVector<AlertRow> m_rows;
    const int m_maxRows = 10000;
};
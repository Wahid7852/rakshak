#include "rakshak/models/PoliciesModel.h"
#include <QtGui/QStandardItemModel>

PoliciesModel::PoliciesModel(QObject* parent) : QStandardItemModel(parent) {
    setHorizontalHeaderLabels({"Policy", "Value"});
}